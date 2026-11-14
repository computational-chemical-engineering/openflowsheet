"""`syn001.column`'s answer judged: S02 spec §8 acceptance, §1.7 products, §2's overall closure
(A08) and the spec values (A06).

Moved verbatim from `column_solve` (S19 B3), which re-exports every public name here and keeps the
solve path. This module imports only `column_compile` among the column's solve modules.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.models import flow_id, temperature_id
from openflowsheet.models.syn001.cascade import (
    _enthalpy_flow,
    _phase,
    inlet_stream,
    liquid_id,
    liquid_total_id,
    stage_duty_id,
    stage_pressure_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade_solve import (
    DECLARATION_CONTEXT,
    TWO_PHASE_SATURATION_TOLERANCE,
    saturation_pairs,
)
from openflowsheet.models.syn001.column import (
    INVERSE_KINDS,
    ColumnSpec,
    component_feeds,
    distillate_id,
    distillate_total_id,
    product_total_id,
    purity_reference,
    reflux_fraction_id,
    reflux_id,
    regime_form,
    specified_quantity,
)
from openflowsheet.models.syn001.column_compile import stage_unit
from openflowsheet.models.syn001.tp_state import single_phase_admissible
from openflowsheet.orchestrator.region import KIND_TOLERANCE, LABEL_KIND, Regime
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

#: S06 §8 item 4: the binary64 slack on a recovery's and a purity's bound, `2⁻⁵²`.
QUOTIENT_SLACK: Final = 2.0**-52


#: The prefix of every item-6 failure string of `acceptance_failures`.
ITEM_6_PREFIX: Final = "§8.6: "


# -- spec §8: acceptance -------------------------------------------------------------------------


#: An attempt signature's value as a stage regime; any other value is a defect (`KeyError`).
_REGIMES: Final[Mapping[str, Regime]] = {
    "TWO_PHASE": "TWO_PHASE",
    "LIQUID": "LIQUID",
    "VAPOR": "VAPOR",
    "ZERO_FLOW": "ZERO_FLOW",
}


def regimes_of(spec: ColumnSpec, signature: Sequence[tuple[str, str]]) -> dict[int, Regime]:
    """A region signature's regimes by equilibrium stage."""
    found = dict(signature)
    return {j: _REGIMES[found[stage_unit(spec.unit_id, j)]] for j in spec.equilibrium_stages()}


def system_residuals(
    spec: ColumnSpec,
    declared: ProblemSpec,
    state: Mapping[str, float],
    regimes: Mapping[int, Regime],
) -> tuple[dict[str, float], tuple[str, ...]]:
    """The declared rows of the signature (pins, drops and labels applied), evaluated by the
    float reference evaluator at `state`, and the pinned columns."""
    values = row_values(declared, state)
    dropped: set[str] = set()
    pinned: list[str] = []
    labels: list[tuple[str, str, str]] = []
    for stage, regime in regimes.items():
        form = regime_form(spec, stage, regime)
        dropped.update(form.dropped)
        pinned.extend(form.pinned)
        if form.swapped:
            dropped.add(form.swapped)
        if form.label is not None:
            labels.append(form.label)
    residuals = {name: value for name, value in values.items() if name not in dropped}
    for row, outlet, source in labels:
        residuals[row] = float(state[outlet]) - float(state[source])
    return residuals, tuple(pinned)


def singular_pairs(regimes: Mapping[int, Regime]) -> tuple[tuple[int, int], ...]:
    """Spec §4.3: the adjacent equilibrium stages `(j, j+1)` whose pair is structurally singular
    — j emits no vapour (`LIQUID`) and j+1 emits vapour (`TWO_PHASE`, `VAPOR`), or j emits liquid
    (`TWO_PHASE`, `LIQUID`) and j+1 is `VAPOR`."""
    found: list[tuple[int, int]] = []
    for j, regime in regimes.items():
        below = regimes.get(j + 1)
        if below is None:
            continue
        if (regime == "LIQUID" and below in ("TWO_PHASE", "VAPOR")) or (
            regime in ("TWO_PHASE", "LIQUID") and below == "VAPOR"
        ):
            found.append((j, j + 1))
    return tuple(found)


def _admissibility(
    spec: ColumnSpec,
    provider: PropertyProvider,
    state: Mapping[str, float],
    stage: int,
    regime: Phase,
) -> tuple[bool, str]:
    """S01 §8's R-007 admissibility of a single-phase stage's outlet (S01 §17.3)."""
    unit, components = spec.unit_id, spec.components
    outlet = liquid_id if regime == "LIQUID" else vapor_id
    stream = StreamState(
        n=tuple(float(state[outlet(unit, stage, c)]) for c in components),
        temperature=float(state[stage_temperature_id(unit, stage)]),
        pressure=float(state[stage_pressure_id(unit, stage)]),
    )
    admissible, _, error, status, message = single_phase_admissible(
        provider, stream, regime, components, DECLARATION_CONTEXT
    )
    return admissible, (f"equivalent temperature error {error!r} K" if status == "ok" else message)


def _saturation_pairs(
    spec: ColumnSpec,
    provider: PropertyProvider,
    state: Mapping[str, float],
    regimes: Mapping[int, Regime],
) -> dict[int, tuple[float, float]]:
    """S08 §5.5's pairs for a column: `cascade_solve.saturation_pairs` on its stages (S08b §5.2)."""
    return saturation_pairs(spec.unit_id, spec.components, provider, state, regimes)


def saturation_errors(
    spec: ColumnSpec,
    provider: PropertyProvider,
    state: Mapping[str, float],
    regimes: Mapping[int, Regime],
) -> dict[int, float]:
    """S08 §5.5 (S02 §8 item 6): for every `TWO_PHASE` stage `j`, the larger of
    `|T_j − T_bub(l_j, P_j)|` and `|T_j − T_dew(v_j, P_j)|` in K; `inf` where either temperature
    is not `inside` the band. Item 6 holds iff every value is `≤ TWO_PHASE_SATURATION_TOLERANCE`."""
    return {
        stage: max(bubble, dew)
        for stage, (bubble, dew) in _saturation_pairs(spec, provider, state, regimes).items()
    }


def acceptance_failures(
    spec: ColumnSpec,
    provider: PropertyProvider,
    declared: ProblemSpec,
    state: Mapping[str, float],
    regimes: Mapping[int, Regime],
) -> tuple[str, ...]:
    """Spec §8: S01 §8 (every row of the final signature within `KIND_TOLERANCE`, every pinned
    column zero, `V_j, L_j > 0` on a `TWO_PHASE` stage, R-007 admissibility on a single-phase
    one), plus items 1–5. Item 1 is the first clause, over the declared S02 rows (S06 §8 item 1:
    the inverse rows are among them). S06 §8 items 2 and 4 are the defect clauses below; item 3
    is not a defect (`single_phase_specified_stage`). Item 6 is S08 §5.5's saturation
    consistency (`saturation_errors`). Empty when the answer is accepted."""
    failures: list[str] = []
    residuals, pinned = system_residuals(spec, declared, state, regimes)
    for row, value in residuals.items():
        tolerance = KIND_TOLERANCE[declared.row_kinds.get(row, LABEL_KIND)]
        if not abs(value) <= tolerance:
            failures.append(f"row {row} = {value!r} exceeds {tolerance!r}")
    for column in pinned:
        if state[column] != 0.0:
            failures.append(f"pinned column {column} = {state[column]!r} is not zero")
    unit = spec.unit_id
    for stage, regime in regimes.items():
        if regime == "TWO_PHASE":
            for total in (vapor_total_id(unit, stage), liquid_total_id(unit, stage)):
                if not state[total] > 0.0:
                    failures.append(f"TWO_PHASE stage {stage}: {total} = {state[total]!r}")
        elif regime in ("LIQUID", "VAPOR"):
            phase: Phase = "LIQUID" if regime == "LIQUID" else "VAPOR"
            admissible, detail = _admissibility(spec, provider, state, stage, phase)
            if not admissible:
                failures.append(f"{regime} stage {stage} inadmissible: {detail}")
    # Item 2: a partial end stage under a ratio or rate specification is TWO_PHASE (§4.2); S06
    # §8 item 2: also under `purity`, `recovery` or a `temperature` of another stage. A
    # `temperature` of the end stage itself is S06 §8 item 3's, not a defect.
    for end in spec.ends():
        given = spec.end_specification(end)
        stage = spec.end_stage(end)
        if spec.end_kind(end) == "partial" and given is not None and given.kind != "duty":
            if given.kind == "temperature" and given.stage == stage:
                continue
            if regimes[stage] != "TWO_PHASE":
                failures.append(f"§8.2: {end} stage {stage} under {given.kind} is {regimes[stage]}")
    # Item 3: a total condenser needs V_2 > 0 and 0 < phi < 1 (§2.2).
    if spec.total_condenser:
        v_2, phi = state[vapor_total_id(unit, 2)], state[reflux_fraction_id(unit)]
        if not v_2 > 0.0:
            failures.append(f"§8.3: V_2 = {v_2!r}")
        if not 0.0 < phi < 1.0:
            failures.append(f"§8.3: phi = {phi!r}")
    # Item 4: no singular adjacent pair (§4.3).
    for pair in singular_pairs(regimes):
        failures.append(f"§8.4: stages {pair} are a singular adjacent pair")
    # Item 5: a pinned zero product flow is +0.0 (ADR 0001 D3.1, sign bit).
    held = set(pinned)
    for port, flows in product_columns(spec).items():
        for column in flows:
            value = state[column]
            if column in held and value == 0.0 and math.copysign(1.0, value) < 0.0:
                failures.append(f"§8.5: product {port} column {column} is -0.0")
    # Item 6 (S08 §5.5): every TWO_PHASE stage sits at the bubble temperature of its liquid and
    # the dew temperature of its vapour; the rows alone admit a near-trivial split (S08 §3 F4).
    for stage, errors in _saturation_pairs(spec, provider, state, regimes).items():
        for side, error in zip(("bubble", "dew"), errors, strict=True):
            if not error <= TWO_PHASE_SATURATION_TOLERANCE:
                failures.append(f"{ITEM_6_PREFIX}TWO_PHASE stage {stage}: {side} error {error!r} K")
    # S06 §8 item 4: every inverse quantity meets its target within the bound its rows imply.
    for end in spec.ends():
        given = spec.end_specification(end)
        if given is None or given.kind not in INVERSE_KINDS:
            continue
        quantity = specified_quantity(spec, end, state)
        bound = target_bound(spec, end, state)
        if not abs(quantity - given.value) <= bound:
            failures.append(
                f"S06 §8.4: {end} {given.kind} = {quantity!r}, target {given.value!r}, "
                f"bound {bound!r}"
            )
    return tuple(failures)


def target_bound(spec: ColumnSpec, end: str, state: Mapping[str, float]) -> float:
    """S06 §8 item 4: the bound the rows imply on `|q − q*|` at `state`: `τ_T` (temperature),
    `τ_mf / F_c + 2⁻⁵²` (recovery), `(τ_mf + τ_eq / P) / F + 2⁻⁵²` (purity), with the kind
    tolerances of `KIND_TOLERANCE` and `P` the end's product total at `state`."""
    given = spec.end_specification(end)
    assert given is not None and given.kind in INVERSE_KINDS, "an inverse end"
    if given.kind == "temperature":
        return KIND_TOLERANCE["temperature"]
    tau_mf, tau_eq = KIND_TOLERANCE["molar_flow"], KIND_TOLERANCE["molar_flow_squared"]
    assert given.component is not None, "validate first"
    if given.kind == "recovery":
        feed = component_feeds(spec)[spec.components.index(given.component)]
        return tau_mf / feed + QUOTIENT_SLACK
    total = float(state[product_total_id(spec, end)])
    return (tau_mf + tau_eq / total) / purity_reference(spec) + QUOTIENT_SLACK


def single_phase_specified_stage(spec: ColumnSpec, regimes: Mapping[int, Regime]) -> int | None:
    """S06 §8 item 3: the first stage (condenser end first) a `temperature` specification names
    whose regime is not `TWO_PHASE`, else `None`. A total condenser's `T_c` has no regime: its
    rows make it a bubble temperature."""
    for end in spec.ends():
        given = spec.end_specification(end)
        if given is None or given.kind != "temperature":
            continue
        assert given.stage is not None, "validate first"
        regime = regimes.get(given.stage)
        if regime is not None and regime != "TWO_PHASE":
            return given.stage
    return None


class UnsupportedAnswerError(RuntimeError):
    """S06 §8 item 3: a `CONVERGED` state the specification's scope does not offer — answered
    `CAPABILITY_UNAVAILABLE` with `cause`, never a success and not a defect."""

    def __init__(self, cause: str, detail: str) -> None:
        super().__init__(f"{cause}: {detail}")
        self.cause = cause
        self.detail = detail


# -- spec §1.7: products, §2: overall closure (A08), spec values (A06) ---------------------------


def product_columns(spec: ColumnSpec) -> dict[str, tuple[str, ...]]:
    """Spec §1.7's outlet ports: `distillate` — `v_1` (partial or none) or `d` (total) — and
    `bottoms` — `l_N`."""
    unit, components = spec.unit_id, spec.components
    if spec.total_condenser:
        distillate = tuple(distillate_id(unit, c) for c in components)
    else:
        distillate = tuple(vapor_id(unit, 1, c) for c in components)
    bottoms = tuple(liquid_id(unit, spec.stage_count, c) for c in components)
    return {"distillate": distillate, "bottoms": bottoms}


def products(spec: ColumnSpec, state: Mapping[str, float]) -> dict[str, tuple[float, ...]]:
    return {
        port: tuple(float(state[column]) for column in columns)
        for port, columns in product_columns(spec).items()
    }


@dataclass(frozen=True)
class Closure:
    """Overall closures at a state: `Σ_k n_ik − distillate_i − bottoms_i` (mol/s) and
    `Σ_j Q_j + Σ_k Ḣ_k − Ḣ(distillate) − Ḣ(bottoms)` (W)."""

    components: tuple[float, ...]
    energy: float


def overall_closure(
    spec: ColumnSpec, provider: PropertyProvider, state: Mapping[str, float]
) -> Closure:
    unit, components, count = spec.unit_id, spec.components, spec.stage_count
    inlets = spec.inlets()
    ports = products(spec, state)
    per_component = tuple(
        sum(float(state[flow_id(inlet_stream(unit, inlet.port), c)]) for inlet in inlets)
        - ports["distillate"][i]
        - ports["bottoms"][i]
        for i, c in enumerate(components)
    )
    h_in = sum(
        _enthalpy_flow(
            provider,
            DECLARATION_CONTEXT,
            components,
            [float(state[flow_id(inlet_stream(unit, inlet.port), c)]) for c in components],
            float(state[temperature_id(inlet_stream(unit, inlet.port))]),
            inlet.state.pressure,
            _phase(inlet.state),
        )
        for inlet in inlets
    )

    def outflow(port: str, stage: int, phase: Phase) -> float:
        return _enthalpy_flow(
            provider,
            DECLARATION_CONTEXT,
            components,
            list(ports[port]),
            float(state[stage_temperature_id(unit, stage)]),
            float(state[stage_pressure_id(unit, stage)]),
            phase,
        )

    duties = sum(float(state[stage_duty_id(unit, j)]) for j in range(1, count + 1))
    top: Phase = "LIQUID" if spec.total_condenser else "VAPOR"
    energy = duties + h_in - outflow("distillate", 1, top) - outflow("bottoms", count, "LIQUID")
    return Closure(per_component, energy)


def spec_values(spec: ColumnSpec, state: Mapping[str, float]) -> dict[str, float]:
    """`ref.cases.*.spec_values` at a state: `Q_1`, `Q_N`, and per present end its ratio and
    rate (reflux ratio `L_1/V_1` or `Σ r/D`, distillate `V_1` or `D`; boil-up ratio
    `V_N/L_N`, bottoms `L_N`); per inverse end (S06) `<end>_<kind>`, its quantity of
    `specified_quantity`."""
    unit, count = spec.unit_id, spec.stage_count
    values = {
        "condenser_duty": float(state[stage_duty_id(unit, 1)]),
        "reboiler_duty": float(state[stage_duty_id(unit, count)]),
    }
    if spec.condenser != "none":
        if spec.total_condenser:
            reflux = sum(float(state[reflux_id(unit, c)]) for c in spec.components)
            distillate = float(state[distillate_total_id(unit)])
        else:
            reflux = float(state[liquid_total_id(unit, 1)])
            distillate = float(state[vapor_total_id(unit, 1)])
        values["reflux_ratio"] = reflux / distillate
        values["distillate_rate"] = distillate
    if spec.reboiler != "none":
        bottoms = float(state[liquid_total_id(unit, count)])
        values["boilup_ratio"] = float(state[vapor_total_id(unit, count)]) / bottoms
        values["bottoms_rate"] = bottoms
    for end in spec.ends():
        given = spec.end_specification(end)
        if given is not None and given.kind in INVERSE_KINDS:
            values[f"{end}_{given.kind}"] = specified_quantity(spec, end, state)
    return values
