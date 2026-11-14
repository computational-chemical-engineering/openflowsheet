"""`syn001.column`'s easy endpoint and inverse records: S02 spec §18.2's `s02-bubble-point-v1`
(bubble-point sweeps at fixed CMO stage ratios) and S06 §7.3 and §7.5's inverse records and
unreached report.

Moved verbatim from `column_solve` (S19 B3), which re-exports every public name here and keeps the
solve path. This module imports nothing from `column_solve`, `column_blocks` or the other column
modules that solve.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from openflowsheet.models.syn001.cascade import CascadeFailure, _k_values, _parameter, thomas
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
from openflowsheet.models.syn001.column import (
    INVERSE_KINDS,
    PHI_INITIAL,
    ColumnSpec,
    ProfileInitial,
    _initial_state,
    component_feeds,
    inverse_parameter,
    purity_reference,
    slot_column,
    specified_quantity,
)
from openflowsheet.models.syn001.equilibrium_form import composition_dependent
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.orchestrator.homotopy import HomotopyRecord
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.trace import fraction_string
from openflowsheet.thermo import PropertyProvider

#: Spec §18.2's registered easy endpoint, the target's `initializer_source`.
PRESOLVE_ID: Final = "s02-bubble-point-v1"


#: §18.2 step 3d: the sweeps stop at `max_j |ΔT_j| ≤ 1e-9 K`, after at most 500 sweeps.
SWEEP_TOLERANCE: Final = 1e-9


MAX_SWEEPS: Final = 500


#: S10-C design note §4.9, composition-dependent K only: the sweeps evaluate K at the liquid
#: composition relaxed by `ω` (`x̄_j^m = ω x_j^m + (1 − ω) x̄_j^{m−1}`; undamped, C-EW
#: oscillates), and stop only once `max_{j,i} |x_ij^m − x̄_ij^{m−1}| ≤ 1e-10` as well.
SWEEP_RELAXATION: Final = 0.5


SWEEP_COMPOSITION_TOLERANCE: Final = 1e-10


# -- spec §18.2: the easy endpoint `s02-bubble-point-v1` ----------------------------------------


@dataclass(frozen=True)
class BubblePointEndpoint:
    """§18.2's `x⁰` and its records (§18.2 "Records"): the stage ratios `ρ_j` by equilibrium
    stage, `φ` (a total condenser's, else `None`), the sweep count and the last `max_j |ΔT_j|`."""

    #: Every declared column, in `declared_rows` order.
    state: Mapping[str, float]
    rho: Mapping[int, float]
    phi: float | None
    sweeps: int
    last_delta: float


def stage_ratios(
    spec: ColumnSpec, initial: ProfileInitial, *, ratio_scale: float = 1.0
) -> tuple[dict[int, float], float | None]:
    """§18.2 step 1: `ρ_j = V_j^cmo / L_j^cmo` (×`ratio_scale`, A14's hook) on every equilibrium
    stage, except a partial condenser under `reflux_ratio` (`ρ_1 = 1/RR*`) and a partial reboiler
    under `boilup_ratio` (`ρ_N = BR*`), which the specification holds; and a total condenser's
    `φ` — `RR*/(1 + RR*)` under `reflux_ratio`, else `φ⁰`."""
    rho = {
        j: ratio_scale * (initial.vapor_cmo[j - 1] / initial.liquid_cmo[j - 1])
        for j in spec.equilibrium_stages()
    }
    phi: float | None = None
    for end in spec.ends():
        given = spec.end_specification(end)
        kind = None if given is None else given.kind
        if spec.end_kind(end) == "total":
            assert given is not None
            phi = given.value / (1.0 + given.value) if kind == "reflux_ratio" else PHI_INITIAL
        elif given is not None and kind == "reflux_ratio":
            rho[spec.end_stage(end)] = 1.0 / given.value
        elif given is not None and kind == "boilup_ratio":
            rho[spec.end_stage(end)] = given.value
    return rho, phi


def sweep_flows(
    spec: ColumnSpec,
    provider: PropertyProvider,
    temperatures: Mapping[int, float],
    rho: Mapping[int, float],
    phi: float | None,
    compositions: Mapping[int, Sequence[float]] | None = None,
) -> tuple[dict[int, list[float]], dict[int, list[float]]]:
    """§18.2 steps 3a–3b: `K_ij` at `(T_j, P_j*)` (a composition-dependent form: at the relaxed
    liquid `compositions[j]`, S10-C §4.9), then per component §6 step 4's tridiagonal with
    `S_ij = K_ij ρ_j` (total condenser: first diagonal `−(1 + S_i2) + φ S_i2`); `l_ij` its
    solution, `v_ij = S_ij l_ij`."""
    components, count = spec.components, spec.stage_count
    stages = spec.equilibrium_stages()
    inlets = spec.inlets()
    k_stage = {
        j: _k_values(
            provider,
            DECLARATION_CONTEXT,
            components,
            temperatures[j],
            spec.pressures[j - 1],
            liquid=None if compositions is None else compositions[j],
        )
        for j in stages
    }
    liquid = {j: [0.0] * len(components) for j in stages}
    vapor = {j: [0.0] * len(components) for j in stages}
    for i in range(len(components)):
        strip = {j: k_stage[j][i] * rho[j] for j in stages}
        diag = [-(1.0 + strip[j]) for j in stages]
        if phi is not None:
            diag[0] += phi * strip[stages[0]]
        solved = thomas(
            [1.0] * len(stages),
            diag,
            [strip[j + 1] if j < count else 0.0 for j in stages],
            [-sum(f.state.n[i] for f in inlets if f.stage == j) for j in stages],
        )
        for k, j in enumerate(stages):
            liquid[j][i] = solved[k]
            vapor[j][i] = strip[j] * solved[k]
    return liquid, vapor


def liquid_compositions(
    liquid: Mapping[int, Sequence[float]], stages: Sequence[int]
) -> dict[int, tuple[float, ...]]:
    """`x_j = l_j/L_j` on `stages` (S10-C §4.9's `x̄_j⁰` from §6's Thomas solution)."""
    compositions: dict[int, tuple[float, ...]] = {}
    for j in stages:
        total = sum(liquid[j])
        compositions[j] = tuple(a / total for a in liquid[j])
    return compositions


def relaxed_compositions(
    previous: Mapping[int, Sequence[float]],
    liquid: Mapping[int, Sequence[float]],
    stages: Sequence[int],
) -> tuple[dict[int, tuple[float, ...]], float]:
    """S10-C §4.9: `x_j^m = l_j^m/L_j^m`, `x̄_j^m = ω x_j^m + (1 − ω) x̄_j^{m−1}` with
    `ω = SWEEP_RELAXATION`, and the stop measure `max_{j,i} |x_ij^m − x̄_ij^{m−1}|`."""
    omega = SWEEP_RELAXATION
    current = liquid_compositions(liquid, stages)
    change = 0.0
    relaxed: dict[int, tuple[float, ...]] = {}
    for j in stages:
        change = max(change, max(abs(a - b) for a, b in zip(current[j], previous[j], strict=True)))
        relaxed[j] = tuple(
            omega * a + (1.0 - omega) * b for a, b in zip(current[j], previous[j], strict=True)
        )
    return relaxed, change


def _bubble_temperature(
    provider: PropertyProvider, flows: Sequence[float], pressure: float, where: str
) -> float | CascadeFailure:
    """§18.2 step 3c: the bubble temperature (ADR 0012 D1's `T(β = 0)`); outside the domain ends
    typed."""
    band = band_temperature(provider, flows, pressure, 0.0, DECLARATION_CONTEXT)
    if band.position != "inside" or band.temperature is None:
        return CascadeFailure(
            "INITIALIZATION_FAILED",
            f"initialization_failed({PRESOLVE_ID}, bubble_point_outside_domain)",
            f"{where}: the bubble temperature at P = {pressure!r} Pa is {band.position} the domain",
        )
    return band.temperature


def bubble_point_endpoint(
    spec: ColumnSpec,
    provider: PropertyProvider,
    initial: ProfileInitial,
    *,
    profile_shift: float = 0.0,
    ratio_scale: float = 1.0,
    max_sweeps: int = MAX_SWEEPS,
) -> BubblePointEndpoint | CascadeFailure:
    """Spec §18.2 `s02-bubble-point-v1`: sweeps from §6's profile (`+ profile_shift`, K) at the
    stage ratios of step 1 (`ratio_scale` on those no specification holds; A14's hooks) until
    `max_j |ΔT_j| ≤ 1e-9 K`, final flows at the stopped `T`, and `x⁰` by §6 steps 5–6.

    A composition-dependent form (S10-C §4.9) evaluates K at the relaxed liquid composition
    `x̄` (from §6's Thomas solution) and also needs `max |x^m − x̄^{m−1}| ≤ 1e-10` to stop; the
    final flows use the relaxed `x̄` at the stop. SYN-001 applies neither."""
    unit = spec.unit_id
    stages = spec.equilibrium_stages()
    rho, phi = stage_ratios(spec, initial, ratio_scale=ratio_scale)
    temperatures = {j: initial.profile[j - 1] + float(profile_shift) for j in stages}
    compositions = (
        liquid_compositions(initial.liquid, stages) if composition_dependent(provider) else None
    )
    sweeps, delta, change = 0, math.inf, 0.0
    for sweep in range(1, max_sweeps + 1):
        liquid, _ = sweep_flows(spec, provider, temperatures, rho, phi, compositions)
        updated: dict[int, float] = {}
        for j in stages:
            found = _bubble_temperature(
                provider, liquid[j], spec.pressures[j - 1], f"{unit} stage {j}, sweep {sweep}"
            )
            if isinstance(found, CascadeFailure):
                return found
            updated[j] = found
        delta = max(abs(updated[j] - temperatures[j]) for j in stages)
        temperatures = updated
        if compositions is not None:
            compositions, change = relaxed_compositions(compositions, liquid, stages)
        if delta <= SWEEP_TOLERANCE and change <= SWEEP_COMPOSITION_TOLERANCE:
            sweeps = sweep
            break
    else:
        detail = "" if compositions is None else f", max |dx| = {change!r}"
        return CascadeFailure(
            "INITIALIZATION_FAILED",
            f"initialization_failed({PRESOLVE_ID}, sweeps_exhausted)",
            f"{unit}: max |dT| = {delta!r} K{detail} after {max_sweeps} sweeps",
        )
    liquid, vapor = sweep_flows(spec, provider, temperatures, rho, phi, compositions)
    profile = [temperatures.get(j, 0.0) for j in range(1, spec.stage_count + 1)]
    if phi is not None:
        found = _bubble_temperature(provider, vapor[2], spec.pressures[0], f"{unit} condenser")
        if isinstance(found, CascadeFailure):
            return found
        profile[0] = found
    state = _initial_state(
        spec,
        provider,
        DECLARATION_CONTEXT,
        liquid,
        vapor,
        tuple(profile),
        phi=PHI_INITIAL if phi is None else phi,
    )
    return BubblePointEndpoint(state, rho, phi, sweeps, delta)


# -- S06 §7.3 and §7.5: inverse records and the unreached report ----------------------------------


@dataclass(frozen=True)
class InverseRecord:
    """S06 §7.5: one inverse slot's records: its end, kind and attribute (component name or
    stage), the user's value (`x*`, `r*`, `T*`), the pinned parameter's id and value (`π*`,
    `ν*`, `T*`), `F` (purity) or `F_c` (recovery) as formed (`None` for a temperature), and at
    `x⁰` the specified quantity `q⁰` and the slot column's value `p⁰`."""

    end: str
    kind: str
    attribute: str | int
    value: float
    parameter_id: str
    parameter: float
    reference: float | None
    q0: float
    p0: float


def _attribute(spec: ColumnSpec, end: str) -> str | int:
    given = spec.end_specification(end)
    assert given is not None
    attribute = given.stage if given.kind == "temperature" else given.component
    assert attribute is not None, "validate first"
    return attribute


def inverse_ends(spec: ColumnSpec) -> tuple[str, ...]:
    """The ends whose specification is an inverse kind, condenser first."""
    return tuple(
        end
        for end in spec.ends()
        if (given := spec.end_specification(end)) is not None and given.kind in INVERSE_KINDS
    )


def inverse_records(spec: ColumnSpec, x0: Mapping[str, float]) -> tuple[InverseRecord, ...]:
    """S06 §7.5 at the easy endpoint `x⁰`, one record per inverse end."""
    found: list[InverseRecord] = []
    for end in inverse_ends(spec):
        given = spec.end_specification(end)
        assert given is not None
        variable = slot_column(spec, end, given.kind)
        reference: float | None = None
        if given.kind == "purity":
            reference = purity_reference(spec)
        elif given.kind == "recovery":
            reference = component_feeds(spec)[spec.components.index(str(_attribute(spec, end)))]
        found.append(
            InverseRecord(
                end=end,
                kind=given.kind,
                attribute=_attribute(spec, end),
                value=given.value,
                parameter_id=_parameter(variable),
                parameter=inverse_parameter(spec, end),
                reference=reference,
                q0=specified_quantity(spec, end, x0),
                p0=float(x0[variable]),
            )
        )
    return tuple(found)


@dataclass(frozen=True)
class UnreachedSpecification:
    """S06 §7.3: an inverse target a non-`CONVERGED` answer did not reach. `lambda_reached` is
    edge 3's last accepted λ (ADR 0010's exact dyadic string) and `value` the specified quantity
    at that λ's state; both `None` when edge 3 did not run or accepted no λ. A report, never an
    infeasibility claim."""

    code: str
    end: str
    kind: str
    attribute: str | int
    target: float
    lambda_reached: str | None
    value: float | None


def lambda_state(failed: RegionResult, record: HomotopyRecord) -> dict[str, float] | None:
    """The state edge 3 accepted at `record.lambda_reached`: the failed solve's item-0 opening
    (the recovery's start, its pins included) with the accepted corrector's `x` over the
    attempt's free columns. `None` when no λ was accepted (the easy endpoint stalled)."""
    if failed.opening is None:
        return None
    accepted = [
        trial
        for trial in record.trials
        if trial.accepted and trial.lambda_value == record.lambda_reached
    ]
    if not accepted:
        return None
    state = {name: float(value) for name, value in failed.opening[0].items()}
    x = accepted[-1].corrector.result.x
    for position, name in enumerate(record.variable_ids):
        state[name] = float(x[position])
    return state


def unreached_specifications(
    spec: ColumnSpec, result: RegionResult, recovered_from: RegionResult | None
) -> tuple[UnreachedSpecification, ...]:
    """S06 §7.3: per inverse end, the report on a non-`CONVERGED` answer (empty otherwise)."""
    if result.outcome == "CONVERGED":
        return ()
    reached: str | None = None
    state: dict[str, float] | None = None
    if recovered_from is not None and result.homotopy is not None:
        state = lambda_state(recovered_from, result.homotopy)
        if state is not None:
            reached = fraction_string(result.homotopy.lambda_reached)
    found: list[UnreachedSpecification] = []
    for end in inverse_ends(spec):
        given = spec.end_specification(end)
        assert given is not None
        found.append(
            UnreachedSpecification(
                code=f"inverse_specification_not_reached({given.kind}:{end})",
                end=end,
                kind=given.kind,
                attribute=_attribute(spec, end),
                target=given.value,
                lambda_reached=reached,
                value=None if state is None else specified_quantity(spec, end, state),
            )
        )
    return tuple(found)
