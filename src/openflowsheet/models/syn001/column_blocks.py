"""Block openings for the SYN-001 column: S08 design note §5.2 and §5.3 (WO-2).

A column whose regular root has a dry section (`VAPOR` stages) or a flooded section (`LIQUID`
stages) reads `V^a 2P^b L^c` from top to bottom (S02 §4.3's block rule, R-533). §5.2 generates
the candidate `(a, c)` pairs from the column's liquid and vapour sources and its fixed stages, a
pure function of the `ColumnSpec`; §5.3 builds each candidate's opening `x⁰`,
`s08-block-endpoint-v1`: bubble-point sweeps over the two-phase core at S02 §18.2's stage ratios
with exact zeros on the L-block, then an energy solve per block stage at its specified duty,
with every pinned flow exactly `+0.0`. Nothing here is solved: the opening is constructed, and a
candidate the construction cannot build is refused with a typed reason. Stage B of S02 §7 step 7
(WO-3) calls the builder; Stage A never does.

The builder reuses §18.2's pieces unchanged (`stage_ratios`, `_k_values`, `thomas`,
`band_temperature`, `_initial_state`) and S02 §8's admissibility test (`_admissibility`, through
`single_phase_admissible`); enthalpies are the provider's (`tp_state.enthalpy_flow`). At the
all-two-phase pair `(0, 0)`, which §5.2 never generates, it reproduces §18.2's `x⁰` (A03).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from openflowsheet.models.syn001.cascade import CascadeFailure, _k_values, thomas
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
from openflowsheet.models.syn001.column import (
    PHI_INITIAL,
    ColumnSpec,
    ProfileInitial,
    _initial_state,
)
from openflowsheet.models.syn001.column_solve import (
    MAX_SWEEPS,
    SWEEP_TOLERANCE,
    _admissibility,
    stage_ratios,
)
from openflowsheet.models.syn001.saturation_band import BandError, band_temperature
from openflowsheet.models.syn001.tp_state import enthalpy_flow
from openflowsheet.orchestrator.region import Regime
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

__all__ = [
    "BLOCK_ENDPOINT_ID",
    "ENERGY_TEMPERATURE_TOLERANCE",
    "MAX_ENERGY_EVALUATIONS",
    "BlockEndpoint",
    "Sources",
    "block_endpoint",
    "block_signature",
    "candidates",
    "sources",
]

#: §5.3: the block endpoint's id, the `initializer_source` of a Stage-B solve and the code
#: of its refusals, `initialization_failed(s08-block-endpoint-v1, <reason>)`.
BLOCK_ENDPOINT_ID: Final = "s08-block-endpoint-v1"
#: §5.3 step 5: a block stage's energy solve stops at `|ΔT| ≤ 1e-12 K`.
ENERGY_TEMPERATURE_TOLERANCE: Final = 1e-12
#: The energy solve's budget of enthalpy evaluations, the two domain ends included. The bracket
#: at least halves every three evaluations, so on a 160 K domain the tolerance is met in < 150.
MAX_ENERGY_EVALUATIONS: Final = 200


# -- §5.2: sources, fixed stages and candidates --------------------------------------------------


@dataclass(frozen=True)
class Sources:
    """§5.2's sets: liquid and vapour sources as `(stage, kind)`, kind `end`, `reflux`, `inlet`
    or `duty`, in a fixed order (ends, then inlets in `spec.inlets()` order, then intermediate
    duties by stage); and the fixed stages, which must be `TWO_PHASE`, ascending."""

    liquid: tuple[tuple[int, str], ...]
    vapor: tuple[tuple[int, str], ...]
    fixed: tuple[int, ...]


def _flows(n: tuple[float, ...]) -> bool:
    """§5.2: an inlet flows when `Σ n > 0`; a dormant inlet is never a source."""
    return sum(n) > 0.0


def sources(spec: ColumnSpec) -> Sources:
    """§5.2's liquid sources, vapour sources and fixed stages of `spec`."""
    count = spec.stage_count
    equilibrium = set(spec.equilibrium_stages())
    liquid: list[tuple[int, str]] = []
    vapor: list[tuple[int, str]] = []
    fixed: set[int] = set()
    if spec.condenser == "partial":
        liquid.append((1, "end"))
    elif spec.total_condenser:
        liquid.append((2, "reflux"))
        fixed.add(2)
    if spec.reboiler == "partial":
        vapor.append((count, "end"))
    for inlet in spec.inlets():
        if not _flows(inlet.state.n):
            continue
        (liquid if inlet.state.phase == "LIQUID" else vapor).append((inlet.stage, "inlet"))
    for stage in sorted(equilibrium):
        duty = spec.duties[stage - 1]
        if duty is not None and duty < 0.0:
            liquid.append((stage, "duty"))
        elif duty is not None and duty > 0.0:
            vapor.append((stage, "duty"))
    for end in spec.ends():
        given = spec.end_specification(end)
        if spec.end_kind(end) == "partial" and (given is None or given.kind != "duty"):
            fixed.add(spec.end_stage(end))
        if given is not None and given.kind == "temperature" and given.stage in equilibrium:
            fixed.add(given.stage)
    return Sources(tuple(liquid), tuple(vapor), tuple(sorted(fixed)))


def _carries(spec: ColumnSpec, stage: int, phase: str) -> bool:
    """§5.2 (V3): `stage` carries a flowing inlet declared `phase`."""
    return any(
        inlet.stage == stage and inlet.state.phase == phase and _flows(inlet.state.n)
        for inlet in spec.inlets()
    )


def _valid(spec: ColumnSpec, found: Sources, a: int, c: int) -> bool:
    """§5.2's (V1)–(V4) for the pair `(a, c)`."""
    stages = spec.equilibrium_stages()
    b = len(stages) - a - c
    if (a, c) == (0, 0):  # (V4): all-2P is Stage A's
        return False
    core = set(stages[a : a + b])
    if not set(found.fixed) <= core:  # (V1)
        return False
    if b >= 1:  # (V2)
        top, bottom = stages[a], stages[a + b - 1]
        return top in {j for j, _ in found.liquid} and bottom in {j for j, _ in found.vapor}
    # (V3)
    if a >= 1 and not _carries(spec, stages[a - 1], "VAPOR"):
        return False
    return not (c >= 1 and not _carries(spec, stages[a], "LIQUID"))


def candidates(spec: ColumnSpec) -> tuple[tuple[int, int], ...]:
    """§5.2: the valid pairs `(a, c)`, `a + c ≤ n`, in ascending `a + c`, then ascending `a`."""
    found = sources(spec)
    n = len(spec.equilibrium_stages())
    return tuple(
        (a, size - a)
        for size in range(1, n + 1)
        for a in range(size + 1)
        if _valid(spec, found, a, size - a)
    )


def block_signature(spec: ColumnSpec, candidate: tuple[int, int]) -> tuple[Regime, ...]:
    """`σ(a, c) = V^a 2P^b L^c` over the equilibrium stages, top to bottom."""
    a, c = candidate
    n = len(spec.equilibrium_stages())
    if a < 0 or c < 0 or a + c > n:
        raise ValueError(f"({a}, {c}) is not a block pair over {n} equilibrium stages")
    vapor: Regime = "VAPOR"
    core: Regime = "TWO_PHASE"
    liquid: Regime = "LIQUID"
    return (vapor,) * a + (core,) * (n - a - c) + (liquid,) * c


# -- §5.3: the block endpoint ---------------------------------------------------------------------


@dataclass(frozen=True)
class BlockEndpoint:
    """§5.3's `x⁰` and its records (§5.6): the candidate's signature over the equilibrium stages,
    the core's stage ratios `ρ_j`, `φ` (a total condenser's, else `None`), the sweep count and the
    last core `max_j |ΔT_j|` (`0` and `0.0` when the core is empty: no sweep runs)."""

    #: Every declared column, in `declared_rows` order.
    state: Mapping[str, float]
    signature: tuple[Regime, ...]
    rho: Mapping[int, float]
    phi: float | None
    sweeps: int
    last_delta: float


class _RefusalError(Exception):
    """A candidate the construction cannot build (§5.3 "Refusals")."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _bubble(provider: PropertyProvider, flows: list[float], pressure: float, where: str) -> float:
    """§5.3 steps 3c and 7: the bubble temperature, or the refusal `bubble_point_outside_domain`
    (a band position other than `inside`) or `bubble_point_refused` (`band_temperature` raises
    `BandError`: a provider refusal or an exhausted bisection; Amendment 1, §13.3)."""
    try:
        band = band_temperature(provider, flows, pressure, 0.0, DECLARATION_CONTEXT)
    except BandError as error:
        raise _RefusalError(
            "bubble_point_refused",
            f"{where}: the bubble temperature at P = {pressure!r} Pa was refused"
            f" ({error.status}): {error.message}",
        ) from error
    if band.position != "inside" or band.temperature is None:
        raise _RefusalError(
            "bubble_point_outside_domain",
            f"{where}: the bubble temperature at P = {pressure!r} Pa is {band.position} the domain",
        )
    return band.temperature


def _core_flows(
    spec: ColumnSpec,
    provider: PropertyProvider,
    carry: tuple[int, ...],
    core: tuple[int, ...],
    temperatures: Mapping[int, float],
    rho: Mapping[int, float],
    phi: float | None,
) -> tuple[dict[int, list[float]], dict[int, list[float]]]:
    """§5.3 steps 3a–3b over the liquid-carrying stages `carry` (the core, then the L-block):
    `K_ij` at `(T_j, P_j*)` on the core, per component the tridiagonal with `S_ij = K_ij ρ_j` on
    the core and `0` on the L-block (total condenser: first diagonal `−(1 + S_i2) + φ S_i2`);
    `l_ij` its solution, `v_ij = S_ij l_ij` on the core and exactly `+0.0` on the L-block."""
    components, count = spec.components, spec.stage_count
    inlets = spec.inlets()
    k_stage = {
        j: _k_values(
            provider, DECLARATION_CONTEXT, components, temperatures[j], spec.pressures[j - 1]
        )
        for j in core
    }
    liquid = {j: [0.0] * len(components) for j in carry}
    vapor = {j: [0.0] * len(components) for j in carry}
    for i in range(len(components)):
        strip = {j: (k_stage[j][i] * rho[j] if j in k_stage else 0.0) for j in carry}
        diag = [-(1.0 + strip[j]) for j in carry]
        if phi is not None:
            diag[0] += phi * strip[carry[0]]
        solved = thomas(
            [1.0] * len(carry),
            diag,
            [strip[j + 1] if j < count else 0.0 for j in carry],
            [-sum(f.state.n[i] for f in inlets if f.stage == j) for j in carry],
        )
        for k, j in enumerate(carry):
            liquid[j][i] = solved[k]
            vapor[j][i] = strip[j] * solved[k] if j in k_stage else 0.0
    return liquid, vapor


def _specified_duty(spec: ColumnSpec, stage: int) -> float:
    """§5.3 `Q_j*`: the intermediate duty, or the end's `duty` specification ((V1) guarantees
    one on every block stage)."""
    duty = spec.duties[stage - 1]
    if duty is not None:
        return duty
    end = spec.slot_stages()[stage]
    given = spec.end_specification(end)
    if given is None or given.kind != "duty":
        raise ValueError(f"stage {stage} has no specified duty; it cannot lie in a block")
    return given.value


def _enthalpy(
    provider: PropertyProvider,
    spec: ColumnSpec,
    flows: tuple[float, ...],
    temperature: float,
    pressure: float,
    phase: Phase,
) -> float:
    """The provider's enthalpy flow `Σ n_i h_i^phase(T, P)`, W (`tp_state.enthalpy_flow`); a
    provider refusal refuses the candidate, `block_energy_refused(<status>)`."""
    status, value, message = enthalpy_flow(
        provider,
        StreamState(n=flows, temperature=temperature, pressure=pressure),
        phase,
        spec.components,
        DECLARATION_CONTEXT,
    )
    if status != "ok":
        raise _RefusalError(f"block_energy_refused({status})", message)
    return value


def _energy_temperature(
    residual: Callable[[float], float], domain: tuple[float, float], where: str
) -> float:
    """§5.3 step 5: the zero of `residual` on the provider's `T` domain by safeguarded
    secant–bisection, to `|ΔT| ≤ 1e-12 K`. The secant runs from the domain ends (for SYN-001's
    constant `C_P` the residual is linear and one secant step is exact); a step outside the
    bracket, or a third step in a row that does not halve it, is a bisection. No sign change on
    the domain refuses the candidate: `block_energy_outside_domain`."""
    lo, hi = domain
    g_lo, g_hi = residual(lo), residual(hi)
    if g_lo == 0.0:
        return lo
    if g_hi == 0.0:
        return hi
    if (g_lo > 0.0) == (g_hi > 0.0):
        raise _RefusalError(
            "block_energy_outside_domain",
            f"{where}: the energy residual has one sign on [{lo!r}, {hi!r}] K",
        )
    prev, g_prev, cur, g_cur = lo, g_lo, hi, g_hi
    slow = 0
    for _ in range(MAX_ENERGY_EVALUATIONS - 2):
        width = hi - lo
        secant = cur - g_cur * (cur - prev) / (g_cur - g_prev) if g_cur != g_prev else lo
        trial = secant if lo < secant < hi and slow < 2 else 0.5 * (lo + hi)
        g_trial = residual(trial)
        if g_trial == 0.0 or abs(trial - cur) <= ENERGY_TEMPERATURE_TOLERANCE:
            return trial
        if (g_trial > 0.0) == (g_lo > 0.0):
            lo, g_lo = trial, g_trial
        else:
            hi, g_hi = trial, g_trial
        if hi - lo <= ENERGY_TEMPERATURE_TOLERANCE:
            return trial
        slow = slow + 1 if hi - lo > 0.5 * width else 0
        prev, g_prev, cur, g_cur = cur, g_cur, trial, g_trial
    raise _RefusalError(
        "block_energy_not_converged",
        f"{where}: |dT| > {ENERGY_TEMPERATURE_TOLERANCE!r} K after "
        f"{MAX_ENERGY_EVALUATIONS} evaluations",
    )


def _inlet_enthalpy(provider: PropertyProvider, spec: ColumnSpec, stage: int) -> float:
    """`Σ_inlets H(inlet at its own T, P and declared phase)` over the flowing inlets at `stage`."""
    total = 0.0
    for inlet in spec.inlets():
        if inlet.stage != stage or not _flows(inlet.state.n):
            continue
        phase: Phase = "LIQUID" if inlet.state.phase == "LIQUID" else "VAPOR"
        total += _enthalpy(
            provider,
            spec,
            tuple(float(x) for x in inlet.state.n),
            float(inlet.state.temperature),
            float(inlet.state.pressure),
            phase,
        )
    return total


def _inlet_flows(spec: ColumnSpec, stage: int) -> list[float]:
    """§5.3 `F_ij`: component `i` summed over every flowing inlet at `stage`, either phase."""
    return [
        sum(f.state.n[i] for f in spec.inlets() if f.stage == stage and _flows(f.state.n))
        for i in range(len(spec.components))
    ]


def _block_stage(
    spec: ColumnSpec,
    provider: PropertyProvider,
    stage: int,
    flows: list[float],
    phase: Phase,
    neighbour: tuple[list[float], float, float] | None,
) -> float:
    """§5.3 steps 5–6 for one block stage: `T_j`, the zero of
    `H^phase(flows, T, P_j*) − [H^phase(neighbour) + Σ_inlets H + Q_j*]`, where `neighbour` is the
    stream entering from the adjacent stage in `phase` (flows, its `T`, its `P*`), or `None`."""
    pressure = float(spec.pressures[stage - 1])
    inflow = _inlet_enthalpy(provider, spec, stage) + _specified_duty(spec, stage)
    if neighbour is not None:
        n, temperature, at = neighbour
        inflow = _enthalpy(provider, spec, tuple(n), temperature, at, phase) + inflow
    outlet = tuple(flows)

    def residual(temperature: float) -> float:
        return _enthalpy(provider, spec, outlet, temperature, pressure, phase) - inflow

    domain = provider.describe().domain["T"]
    return _energy_temperature(residual, domain, f"{spec.unit_id} stage {stage}")


def block_endpoint(
    spec: ColumnSpec,
    provider: PropertyProvider,
    initial: ProfileInitial,
    candidate: tuple[int, int],
    *,
    profile_shift: float = 0.0,
    ratio_scale: float = 1.0,
    max_sweeps: int = MAX_SWEEPS,
) -> BlockEndpoint | CascadeFailure:
    """§5.3 `s08-block-endpoint-v1` for the pair `candidate = (a, c)` on a validated `spec` with
    §6's `initial`; `profile_shift`, `ratio_scale` and `max_sweeps` are §18.2's hooks, passed
    through. A refusal is `INITIALIZATION_FAILED` with cause
    `initialization_failed(s08-block-endpoint-v1, <reason>)`; it never ends a solve by itself."""
    try:
        return _build(
            spec, provider, initial, candidate, float(profile_shift), ratio_scale, max_sweeps
        )
    except _RefusalError as refusal:
        return CascadeFailure(
            "INITIALIZATION_FAILED",
            f"initialization_failed({BLOCK_ENDPOINT_ID}, {refusal.reason})",
            refusal.message,
        )


def _build(
    spec: ColumnSpec,
    provider: PropertyProvider,
    initial: ProfileInitial,
    candidate: tuple[int, int],
    profile_shift: float,
    ratio_scale: float,
    max_sweeps: int,
) -> BlockEndpoint:
    unit, components = spec.unit_id, spec.components
    signature = block_signature(spec, candidate)
    stages = spec.equilibrium_stages()
    a, c = candidate
    b = len(stages) - a - c
    core, l_block, v_block = stages[a : a + b], stages[a + b :], stages[:a]
    # Step 1: the ratios (used on the core).
    rho_all, phi = stage_ratios(spec, initial, ratio_scale=ratio_scale)
    rho = {j: rho_all[j] for j in core}
    liquid = {j: [0.0] * len(components) for j in stages}
    vapor = {j: [0.0] * len(components) for j in stages}
    temperatures: dict[int, float] = {}
    sweeps, delta = 0, 0.0
    if b >= 1:
        carry = stages[a:]
        # Step 2: the start; step 3: the sweeps over the core.
        temperatures = {j: initial.profile[j - 1] + profile_shift for j in core}
        delta = float("inf")
        for sweep in range(1, max_sweeps + 1):
            flows, _ = _core_flows(spec, provider, carry, core, temperatures, rho, phi)
            updated = {
                j: _bubble(
                    provider,
                    flows[j],
                    spec.pressures[j - 1],
                    f"{unit} stage {j}, sweep {sweep}",
                )
                for j in core
            }
            delta = max(abs(updated[j] - temperatures[j]) for j in core)
            temperatures = updated
            if delta <= SWEEP_TOLERANCE:
                sweeps = sweep
                break
        else:
            raise _RefusalError(
                "sweeps_exhausted",
                f"{unit}: core max |dT| = {delta!r} K after {max_sweeps} sweeps",
            )
        # Step 4: the final flows at the stopped T.
        flows, rising = _core_flows(spec, provider, carry, core, temperatures, rho, phi)
        for j in carry:
            liquid[j] = flows[j]
            vapor[j] = rising[j]
    # Step 5: the L-block, top-down.
    for j in l_block:
        above = j - 1
        carried = above in core or above in l_block
        if b == 0:
            feed = _inlet_flows(spec, j)
            upper = liquid[above] if carried else [0.0] * len(components)
            liquid[j] = [upper[i] + feed[i] for i in range(len(components))]
        vapor[j] = [0.0] * len(components)
        neighbour = (
            (liquid[above], temperatures[above], float(spec.pressures[above - 1]))
            if carried
            else None
        )
        temperatures[j] = _block_stage(spec, provider, j, liquid[j], "LIQUID", neighbour)
    # Step 6: the V-block, bottom-up.
    for j in reversed(v_block):
        below = j + 1
        rising_in = below in core or below in v_block
        feed = _inlet_flows(spec, j)
        lower = vapor[below] if rising_in else [0.0] * len(components)
        vapor[j] = [lower[i] + feed[i] for i in range(len(components))]
        liquid[j] = [0.0] * len(components)
        neighbour = (
            (vapor[below], temperatures[below], float(spec.pressures[below - 1]))
            if rising_in
            else None
        )
        temperatures[j] = _block_stage(spec, provider, j, vapor[j], "VAPOR", neighbour)
    # Step 7: the total condenser.
    profile = [temperatures.get(j, 0.0) for j in range(1, spec.stage_count + 1)]
    if phi is not None:
        profile[0] = _bubble(provider, vapor[2], spec.pressures[0], f"{unit} condenser")
    # Step 8: x⁰.
    state = _initial_state(
        spec,
        provider,
        DECLARATION_CONTEXT,
        liquid,
        vapor,
        tuple(profile),
        phi=PHI_INITIAL if phi is None else phi,
    )
    # Step 9: admissibility of every block stage's single phase.
    blocks: list[tuple[int, Phase]] = [(j, "LIQUID") for j in l_block]
    blocks += [(j, "VAPOR") for j in v_block]
    for j, regime in blocks:
        admissible, message = _admissibility(spec, provider, state, j, regime)
        if not admissible:
            raise _RefusalError(f"inadmissible_endpoint({j})", f"{unit} stage {j}: {message}")
    return BlockEndpoint(state, signature, rho, phi, sweeps, delta)
