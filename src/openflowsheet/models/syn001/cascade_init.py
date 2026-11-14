"""`syn001.cascade`'s initializer: S01 spec §6's analytic `s01-kremser-cmo-v1` (CMO totals,
Kremser-type component profiles by the Thomas algorithm) and the initial state.

Moved verbatim from `cascade` (S19 B4), which re-exports every name here and keeps the §5
refusals, the §4.2 regime forms and the §4.6 dormant answer. This module imports only
`cascade_spec` and `cascade_rows` among the cascade modules.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from openflowsheet.canonical import normalize_zero
from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.syn001.cascade_failure import CascadeFailure
from openflowsheet.models.syn001.cascade_rows import declared_problem, declared_rows
from openflowsheet.models.syn001.cascade_spec import (
    BOTTOM,
    TOP,
    CascadeSpec,
    energy_row_id,
    inlet_stream,
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_duty_id,
    stage_pressure_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.equilibrium_form import composition_dependent
from openflowsheet.models.syn001.gamma_phi import _ln_k
from openflowsheet.models.syn001.saturation_band import BandError, band_temperature
from openflowsheet.thermo import PropertyProvider, PropertyRequest, StreamState

#: Spec §6's registered initializer.
INITIALIZER_ID: Final = "s01-kremser-cmo-v1"


#: Spec §6.2 (DECISION 7): `β̄` is clamped to this interval, and each CMO total is floored at
#: `CMO_FLOOR · F`.
BETA_BOUNDS: Final = (0.1, 0.9)


CMO_FLOOR: Final = 0.1


#: `K_i(T, P)` in component order. The initializer's injection point (spec §10 A02).
KValues = Callable[[float, float], Sequence[float]]


def _k_values(
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
    temperature: float,
    pressure: float,
    *,
    liquid: Sequence[float] | None = None,
) -> tuple[float, ...]:
    """`K_i(T, P)` from the provider's `lnK`, as the rows' `LnKBlock` asks for it.

    For a composition-dependent form (S10-C design note §4.9) `K_i(T, P, liquid)` from
    `gamma_phi`'s `ln φ_i^L` at the liquid `liquid` (a composition or flows), which is then
    required (`ValueError` if `None`); SYN-001 ignores `liquid` and makes today's call.
    """
    if composition_dependent(provider):
        if liquid is None:
            raise ValueError("a composition-dependent K needs the liquid it is evaluated at")
        try:
            values, _, _ = _ln_k(provider, components, temperature, pressure, liquid, context, ())
        except BandError as error:
            raise RuntimeError(
                f"lnK at T = {temperature!r} K, P = {pressure!r} Pa: {error.status}: "
                f"{error.message}"
            ) from error
        return tuple(math.exp(value) for value in values)
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(
                n=(1.0,) * len(components), temperature=temperature, pressure=pressure
            ),
            phase="LIQUID",
            properties=("lnK",),
        ),
        context,
    )
    if result.status != "ok":
        raise RuntimeError(
            f"lnK at T = {temperature!r} K, P = {pressure!r} Pa: {result.status}: {result.message}"
        )
    return tuple(math.exp(result.values[f"lnK_{name}"]) for name in components)


# -- spec §6: the initializer --------------------------------------------------------------------


@dataclass(frozen=True)
class KremserInitial:
    """`x_K` of spec §6 and the intermediate quantities A03 checks."""

    z: tuple[float, ...]
    beta: float
    beta_clamped: float
    pbar: float
    tbar: float
    #: `L_j`, `V_j` of step 4 (CMO, floored), before step 5 replaces them by the sums.
    liquid_cmo: tuple[float, ...]
    vapor_cmo: tuple[float, ...]
    #: `l_ij`, `v_ij`, indexed `[j - 1][i]`.
    liquid: tuple[tuple[float, ...], ...]
    vapor: tuple[tuple[float, ...], ...]
    #: Every declared column, in `declared_rows` order.
    state: Mapping[str, float]
    initializer: str = INITIALIZER_ID


def thomas(
    sub: Sequence[float], diag: Sequence[float], sup: Sequence[float], rhs: Sequence[float]
) -> list[float]:
    """The Thomas algorithm without pivoting (spec §6.5): stable on the cascade's weakly
    column-diagonally-dominant, irreducible matrix. `sub[0]` and `sup[-1]` are not read."""
    n = len(diag)
    c = [0.0] * n
    d = [0.0] * n
    c[0], d[0] = sup[0] / diag[0], rhs[0] / diag[0]
    for j in range(1, n):
        m = diag[j] - sub[j] * c[j - 1]
        c[j] = sup[j] / m if j < n - 1 else 0.0
        d[j] = (rhs[j] - sub[j] * d[j - 1]) / m
    out = [0.0] * n
    out[-1] = d[-1]
    for j in range(n - 2, -1, -1):
        out[j] = d[j] - c[j] * out[j + 1]
    return out


def kremser_initial(
    spec: CascadeSpec,
    provider: PropertyProvider,
    context: EvaluationContext,
    *,
    k_values: KValues | None = None,
) -> KremserInitial | CascadeFailure:
    """Spec §6 `s01-kremser-cmo-v1`, on a validated, flowing specification.

    `k_values` replaces the provider's `K_i(T̄, P_j*)` in step 5 only (spec §10 A02 injects a
    constant `K` to reach the Kremser closed form); `T̄` is always the provider's band
    temperature. An all-dormant specification has no initializer: it is §4.6's
    (`dormant_answer`), and asking here is misuse.
    """
    unit, components = spec.unit_id, spec.components
    count = spec.stage_count
    inlets = spec.inlets()
    width = len(components)
    totals = [sum(inlet.state.n[i] for inlet in inlets) for i in range(width)]
    big_f = sum(totals)
    if big_f == 0.0:
        raise ValueError(f"{unit}: every inlet is dormant; spec §4.6 answers it, not §6")
    z = tuple(a / big_f for a in totals)
    beta = sum(sum(i.state.n) for i in inlets if i.state.phase == "VAPOR") / big_f
    beta_clamped = min(max(beta, BETA_BOUNDS[0]), BETA_BOUNDS[1])
    pbar = sum(spec.pressures) / count

    band = band_temperature(provider, totals, pbar, beta_clamped, context)
    if band.position != "inside" or band.temperature is None:
        return CascadeFailure(
            "INITIALIZATION_FAILED",
            f"initialization_failed({INITIALIZER_ID}, tbar_outside_domain)",
            f"{unit}: T(beta = {beta_clamped!r}) at P = {pbar!r} Pa is {band.position} the domain",
        )
    tbar = band.temperature

    floor = CMO_FLOOR * big_f
    liquid_cmo = tuple(
        max(
            sum(sum(i.state.n) for i in inlets if i.state.phase == "LIQUID" and i.stage <= j),
            floor,
        )
        for j in range(1, count + 1)
    )
    vapor_cmo = tuple(
        max(
            sum(sum(i.state.n) for i in inlets if i.state.phase == "VAPOR" and i.stage >= j),
            floor,
        )
        for j in range(1, count + 1)
    )

    def provider_k(temperature: float, pressure: float) -> Sequence[float]:
        return _k_values(provider, context, components, temperature, pressure)

    k_of = k_values if k_values is not None else provider_k
    k_stage = [tuple(k_of(tbar, spec.pressures[j])) for j in range(count)]
    liquid = [[0.0] * width for _ in range(count)]
    vapor = [[0.0] * width for _ in range(count)]
    for i in range(width):
        strip = [k_stage[j][i] * vapor_cmo[j] / liquid_cmo[j] for j in range(count)]
        rhs = [-sum(f.state.n[i] for f in inlets if f.stage == j + 1) for j in range(count)]
        column = thomas(
            [1.0] * count,
            [-(1.0 + strip[j]) for j in range(count)],
            [strip[j + 1] if j + 1 < count else 0.0 for j in range(count)],
            rhs,
        )
        for j in range(count):
            liquid[j][i] = column[j]
            vapor[j][i] = strip[j] * column[j]

    state = _initial_state(spec, provider, context, liquid, vapor, tbar)
    return KremserInitial(
        z=z,
        beta=beta,
        beta_clamped=beta_clamped,
        pbar=pbar,
        tbar=tbar,
        liquid_cmo=liquid_cmo,
        vapor_cmo=vapor_cmo,
        liquid=tuple(tuple(row) for row in liquid),
        vapor=tuple(tuple(row) for row in vapor),
        state=state,
    )


def _inflow_sum(spec: CascadeSpec, values: Mapping[str, float], stage: int, c: str) -> float:
    """The `mix` row's inflow, summed in the row's own order, so `mix` vanishes exactly."""
    unit, count = spec.unit_id, spec.stage_count
    above = flow_id(inlet_stream(unit, TOP), c) if stage == 1 else liquid_id(unit, stage - 1, c)
    below = (
        flow_id(inlet_stream(unit, BOTTOM), c) if stage == count else vapor_id(unit, stage + 1, c)
    )
    total = values[above] + values[below]
    for side in spec.sides:
        if side.stage == stage:
            total = total + values[flow_id(inlet_stream(unit, side.port), c)]
    return total


def _inlet_columns(spec: CascadeSpec) -> dict[str, float]:
    values: dict[str, float] = {}
    for inlet in spec.inlets():
        stream = inlet_stream(spec.unit_id, inlet.port)
        for c, a in zip(spec.components, inlet.state.n, strict=True):
            values[flow_id(stream, c)] = normalize_zero(float(a))
        values[temperature_id(stream)] = float(inlet.state.temperature)
        values[pressure_id(stream)] = float(inlet.state.pressure)
    return values


def _initial_state(
    spec: CascadeSpec,
    provider: PropertyProvider,
    context: EvaluationContext,
    liquid: Sequence[Sequence[float]],
    vapor: Sequence[Sequence[float]],
    tbar: float,
) -> dict[str, float]:
    """Spec §6.5's last step: totals as sums, `T_j = T̄`, `P_j = P_j*`, `m` from `mix`, `Q_j` from
    `energy_j`."""
    unit, components = spec.unit_id, spec.components
    values = _inlet_columns(spec)
    for j in range(spec.stage_count):
        stage = j + 1
        for i, c in enumerate(components):
            values[liquid_id(unit, stage, c)] = liquid[j][i]
            values[vapor_id(unit, stage, c)] = vapor[j][i]
        values[liquid_total_id(unit, stage)] = sum(liquid[j])
        values[vapor_total_id(unit, stage)] = sum(vapor[j])
        values[stage_temperature_id(unit, stage)] = tbar
        values[stage_pressure_id(unit, stage)] = float(spec.pressures[j])
        values[stage_duty_id(unit, stage)] = 0.0
    for stage in range(1, spec.stage_count + 1):
        for c in components:
            values[mixed_id(unit, stage, c)] = _inflow_sum(spec, values, stage, c)
    problem = declared_problem(declared_rows(spec, provider, context))
    residual = row_values(problem, values)
    for stage in range(1, spec.stage_count + 1):
        # energy_j at Q_j = 0 is `0 + Hdot_in - Hdot_out`; Q_j closes it.
        values[stage_duty_id(unit, stage)] = normalize_zero(-residual[energy_row_id(unit, stage)])
    return {name: values[name] for name in problem.variable_ids}
