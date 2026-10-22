"""`syn001.column` compiled and solved: S02 spec §7 and §8 (WO-2), §7.3 as §18.2 (WO-2b).

`column.py` holds the unit layer (WO-1): the specification, its §5 refusals, the §2 rows, the
regime forms and the §6 initializer. This module compiles those rows and runs spec §7's path on
them, calling `orchestrator.region.solve_region` unchanged, through S01's `run_region`:

1. validate (§5); an all-dormant column (possible only without ends, §5 S10) is S01 §4.6's;
2. initialize (`s02-profile-cmo-v1`), giving `x_K`;
3. the easy endpoint `s02-bubble-point-v1` (§18.2, constructed, not solved): bubble-point sweeps
   at fixed CMO stage ratios give an all-two-phase `x⁰` on which every target row except the
   continued `variable − parameter` slot rows holds;
4. the target from `x⁰` under S01's registered `s01-default-v1` (no new policy, spec §0);
5. recovery edge 3 (ADR 0010 D3, ADR 0044's trigger) on its triggers, continuing every
   `variable − parameter` slot from `p⁰` = its column at the opening;

and holds a `CONVERGED` answer to §8 before returning it.

Each equilibrium stage is one lifted split keyed `<U>.stage.<j>`, as S01's (spec §4.1), PH-type.
The total condenser is not a split (§4.1). The withdrawn Newton profile pre-solve's rows
(`presolve_rows`, §7.3) stay here only as the definition of the registered second easy endpoint
`ref.cases.*.presolve` (A06b); they are not on the solve path.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from openflowsheet.canonical import state_sha256
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import EquationSpec, ProblemSpec, QuantityKind
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    SpecificationError,
    flow_id,
    origin,
    temperature_id,
)
from openflowsheet.models.rows import ratio_row, specification_row
from openflowsheet.models.syn001 import TEMPERATURE
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    CascadeSpec,
    DormantAnswer,
    _enthalpy_flow,
    _k_values,
    _parameter,
    _phase,
    declared_problem,
    dormant_answer,
    inlet_stream,
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_duty_id,
    stage_prefix,
    stage_pressure_id,
    stage_row_id,
    stage_temperature_id,
    thomas,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade_solve import (
    DECLARATION_CONTEXT,
    S01_DEFAULT_V1,
    AcceptanceDefectError,
    CompiledCascade,
    run_region,
)
from openflowsheet.models.syn001.cascade_solve import FD_COLUMN_SCALE as CASCADE_FD_SCALE
from openflowsheet.models.syn001.column import (
    MODEL_ID,
    PHI_INITIAL,
    RATIO_KINDS,
    ColumnSpec,
    ProfileInitial,
    _initial_state,
    declared_rows,
    distillate_id,
    distillate_total_id,
    profile_initial,
    ratio_parameter,
    reflux_fraction_id,
    reflux_id,
    regime_form,
    slot_column,
    slot_row_id,
    validate,
)
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.models.syn001.tp_state import single_phase_admissible
from openflowsheet.orchestrator.execution import Region
from openflowsheet.orchestrator.homotopy import Continuation
from openflowsheet.orchestrator.recovery import eo_recovery_due, recovered_provenance
from openflowsheet.orchestrator.region import (
    KIND_TOLERANCE,
    LABEL_KIND,
    ClosureType,
    LiftedSplit,
    RecoveryStart,
    Regime,
    RegionResult,
    ZeroFlowForm,
)
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

#: Spec §18.2's registered easy endpoint, the target's `initializer_source`.
PRESOLVE_ID: Final = "s02-bubble-point-v1"

#: §18.2 step 3d: the sweeps stop at `max_j |ΔT_j| ≤ 1e-9 K`, after at most 500 sweeps.
SWEEP_TOLERANCE: Final = 1e-9
MAX_SWEEPS: Final = 500

#: Spec §7.4: the target's policy is S01's registered `s01-default-v1`, reused (spec §0).
S02_TARGET_POLICY: Final[SolvePolicy] = S01_DEFAULT_V1

#: The withdrawn pre-solve's replacement rows `T_j − T_j⁰` (spec §7.3), kept as the definition of
#: the registered profile endpoint (§18.2, A06b); not on the solve path. A total condenser's
#: replacement `Σ r − 1·D` is the `COL-reflux-ratio` row at `RR = 1`.
PRESOLVE_EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="COL-presolve-T",
        statement=(
            "T_j - T_j0 = 0 in place of each variable - parameter slot row of an equilibrium "
            "stage (the profile pre-solve, S02 spec §7.3)"
        ),
        dependencies=("stage.T", "parameters.T0"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source="docs/derivations/S02-spec.md §7.3",
    ),
)

#: Spec §10 A10's column scales `D_x`: S01's, plus `D_x(phi) = 1` (§2.2).
FD_COLUMN_SCALE: Final[Mapping[QuantityKind, float]] = {**CASCADE_FD_SCALE, "dimensionless": 1.0}

#: `ref.cases.*.continued`'s kind letter of each continued slot.
CONTINUED_KIND: Final[Mapping[str, str]] = {
    "duty": "Q",
    "distillate_rate": "D",
    "bottoms_rate": "B",
}

#: `ref.cases.*.presolve_slots`'s kind letter of a kept ratio row.
RATIO_LETTER: Final[Mapping[str, str]] = {"reflux_ratio": "RR", "boilup_ratio": "BR"}


# -- spec §7.3: the slot substitutions -----------------------------------------------------------


@dataclass(frozen=True)
class Slot:
    """One stage's slot row and its §7.3 substitution (the profile endpoint's rows, A06b). Its
    `parameter`/`variable`/`continued` name the slots edge 3 continues on the path (§18.2).

    `kind` is `ref.cases.*.presolve_slots`' letter: `T` (replaced by `T_j − T_j⁰`), `RR` at a
    total condenser's replaced slot (`Σ r − 1·D`), or the kept ratio's `RR` / `BR`. A replaced
    slot is continued by edge 3: `parameter` is the target's pinned input, `variable` the column
    it pins (`p⁰ = x⁰[variable]`), `continued` its `ref.cases.*.continued` letter."""

    stage: int
    #: The target's slot row id.
    target_row: str
    #: The pre-solve's row id (the target's, for a kept ratio).
    row: str
    kind: str
    value: float
    parameter: str = ""
    variable: str = ""
    continued: str = ""


def slots(spec: ColumnSpec, profile: Sequence[float]) -> tuple[Slot, ...]:
    """Spec §7.3, stage by stage (the total condenser first): every slot row and what the
    pre-solve puts in its place."""
    unit = spec.unit_id
    ends = spec.slot_stages()
    found: list[Slot] = []
    stages = (1, *spec.equilibrium_stages()) if spec.total_condenser else spec.equilibrium_stages()
    for stage in stages:
        end = ends.get(stage)
        if end is None:
            kind, variable = "duty", stage_duty_id(unit, stage)
            target_row = stage_row_id(unit, stage, "Q")
        else:
            given = spec.end_specification(end)
            assert given is not None
            kind = given.kind
            target_row = slot_row_id(unit, stage, kind)
            if kind in RATIO_KINDS:
                found.append(Slot(stage, target_row, target_row, RATIO_LETTER[kind], given.value))
                continue
            variable = slot_column(spec, end, kind)
        common = {"parameter": _parameter(variable), "variable": variable}
        if spec.total_condenser and stage == 1:
            row = slot_row_id(unit, 1, "reflux_ratio")
            found.append(
                Slot(stage, target_row, row, "RR", 1.0, continued=CONTINUED_KIND[kind], **common)
            )
        else:
            row = presolve_row_id(unit, stage)
            found.append(
                Slot(
                    stage,
                    target_row,
                    row,
                    "T",
                    float(profile[stage - 1]),
                    continued=CONTINUED_KIND[kind],
                    **common,
                )
            )
    return tuple(found)


def presolve_row_id(unit: str, stage: int) -> str:
    """`<U>:stage:<j>:T`, the pre-solve's row in place of stage j's slot row (S01's id)."""
    return stage_row_id(unit, stage, "T")


def presolve_rows(rows: Contribution, spec: ColumnSpec, profile: Sequence[float]) -> Contribution:
    """Spec §7.3 (withdrawn from the path by §18.2): the rows whose root is the registered profile
    endpoint `ref.cases.*.presolve` — the declared rows with every replaced slot row replaced. Same
    columns; each replaced slot's pinned input gives way to `T_j*` (`T_j⁰`) or, at a total
    condenser, to the reflux ratio's `RR*` (1), so the slot's column is free."""
    unit, components = spec.unit_id, spec.components
    swap = {slot.target_row: slot for slot in slots(spec, profile) if slot.parameter}
    renamed: dict[str, tuple[str, float]] = {}
    equations: list[EquationSpec] = []
    row_kinds: dict[str, QuantityKind] = {}
    for equation in rows.equations:
        slot = swap.get(equation.equation_id)
        if slot is None:
            equations.append(equation)
            row_kinds[equation.equation_id] = rows.row_kinds[equation.equation_id]
            continue
        if slot.kind == "T":
            parameter = _parameter(stage_temperature_id(unit, slot.stage))
            build = specification_row(stage_temperature_id(unit, slot.stage), parameter)
            family, kind = "COL-presolve-T", "temperature"
        else:
            parameter = ratio_parameter(unit, 1, "reflux_ratio")
            build = ratio_row(
                tuple(reflux_id(unit, c) for c in components), parameter, distillate_total_id(unit)
            )
            family, kind = "COL-reflux-ratio", "molar_flow"
        renamed[slot.parameter] = (parameter, slot.value)
        equations.append(
            EquationSpec(
                equation_id=slot.row,
                build=build,
                accumulation="algebraic",
                origin=origin(MODEL_ID, family),
            )
        )
        row_kinds[slot.row] = kind  # type: ignore[assignment]
    parameter_ids = tuple(renamed[p][0] if p in renamed else p for p in rows.parameter_ids)
    parameters = {(renamed[p][0] if p in renamed else p): v for p, v in rows.parameters.items()}
    for new, value in renamed.values():
        parameters[new] = float(value)
    return replace(
        rows,
        equations=tuple(equations),
        row_kinds=row_kinds,
        parameter_ids=parameter_ids,
        parameters=parameters,
    )


# -- spec §4.1: the per-stage region descriptors -------------------------------------------------


def stage_unit(unit: str, stage: int) -> str:
    """The split's key — its `unit` in every region map and in the attempt signature."""
    return stage_prefix(unit, stage)


def lifted_splits(spec: ColumnSpec) -> tuple[LiftedSplit, ...]:
    """Spec §4.1: each equilibrium stage's `LiftedSplit`, `feed = m_j`, in stage order."""
    unit, components = spec.unit_id, spec.components
    return tuple(
        LiftedSplit(
            unit=stage_unit(unit, stage),
            stream=stage_unit(unit, stage),
            feed=tuple(mixed_id(unit, stage, c) for c in components),
            temperature=stage_temperature_id(unit, stage),
            pressure=stage_pressure_id(unit, stage),
            vapor=tuple(vapor_id(unit, stage, c) for c in components),
            liquid=tuple(liquid_id(unit, stage, c) for c in components),
            vapor_total=vapor_total_id(unit, stage),
            liquid_total=liquid_total_id(unit, stage),
            equilibrium_rows=tuple(stage_row_id(unit, stage, "eq", c) for c in components),
            vapor_definition=stage_row_id(unit, stage, "Vdef"),
            liquid_definition=stage_row_id(unit, stage, "Ldef"),
        )
        for stage in spec.equilibrium_stages()
    )


def zero_flow_forms(spec: ColumnSpec) -> dict[str, ZeroFlowForm]:
    """Each equilibrium stage's `ZERO_FLOW` form from WO-1's `regime_form`, with §2.3's label as
    amended (§17 item 2): always a column."""
    forms: dict[str, ZeroFlowForm] = {}
    for stage in spec.equilibrium_stages():
        form = regime_form(spec, stage, "ZERO_FLOW")
        forms[stage_unit(spec.unit_id, stage)] = ZeroFlowForm(
            unit=stage_unit(spec.unit_id, stage),
            columns=form.pinned,
            rows=(*form.dropped, form.swapped),
            swapped=form.swapped,
            label=form.label,
        )
    return forms


def closure_types(spec: ColumnSpec) -> dict[str, ClosureType]:
    """PH for every equilibrium stage of the target (§18.2's `x⁰` opens them `TWO_PHASE`
    unprojected, T05b §6.4)."""
    return {stage_unit(spec.unit_id, j): "PH" for j in spec.equilibrium_stages()}


def split_temperatures(spec: ColumnSpec) -> dict[str, tuple[str, ...]]:
    return {
        stage_unit(spec.unit_id, j): (stage_temperature_id(spec.unit_id, j),)
        for j in spec.equilibrium_stages()
    }


# -- compile -------------------------------------------------------------------------------------


def model_label(provider: PropertyProvider) -> str:
    """ADR 0002 D2.7, as S01's: the equation set and the property package."""
    capabilities = provider.describe()
    label = (
        f"S02-column-{capabilities.provider_id}"
        f"-{capabilities.implementation_sha256[:12]}-{capabilities.data_sha256[:12]}"
    )
    if len(label) > 64:
        raise SpecificationError(f"the label {label!r} exceeds ADR 0002's 64 characters")
    return label


def compile_column(spec: ColumnSpec, provider: PropertyProvider) -> CompiledCascade:
    """The target's `ProblemSpec`, compiled, and its region: every declared row over every
    declared column."""
    rows = declared_rows(spec, provider, DECLARATION_CONTEXT)
    declared = declared_problem(rows, model_label(provider))
    splits = lifted_splits(spec)
    units = tuple(split.unit for split in splits)
    region = Region(
        units=units,
        row_ids=declared.equation_ids,
        variable_ids=declared.variable_ids,
        eliminated_rows=(),
        signature_units=units,
        fixed_upstream=(),
    )
    return CompiledCascade(
        problem="target",
        spec=declared,
        compiled=compile_problem(declared),
        region=region,
        splits=splits,
        forms=zero_flow_forms(spec),
        types=closure_types(spec),
        temperatures=split_temperatures(spec),
    )


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


def acceptance_failures(
    spec: ColumnSpec,
    provider: PropertyProvider,
    declared: ProblemSpec,
    state: Mapping[str, float],
    regimes: Mapping[int, Regime],
) -> tuple[str, ...]:
    """Spec §8: S01 §8 (every row of the final signature within `KIND_TOLERANCE`, every pinned
    column zero, `V_j, L_j > 0` on a `TWO_PHASE` stage, R-007 admissibility on a single-phase
    one), plus items 1–5. Item 1 is the first clause, over the declared S02 rows. Empty when the
    answer is accepted."""
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
    # Item 2: a partial end stage under a ratio or rate specification is TWO_PHASE (§4.2).
    for end in spec.ends():
        given = spec.end_specification(end)
        stage = spec.end_stage(end)
        if spec.end_kind(end) == "partial" and given is not None and given.kind != "duty":
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
    return tuple(failures)


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
    `V_N/L_N`, bottoms `L_N`)."""
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
    return values


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
) -> tuple[dict[int, list[float]], dict[int, list[float]]]:
    """§18.2 steps 3a–3b: `K_ij` at `(T_j, P_j*)`, then per component §6 step 4's tridiagonal
    with `S_ij = K_ij ρ_j` (total condenser: first diagonal `−(1 + S_i2) + φ S_i2`); `l_ij` its
    solution, `v_ij = S_ij l_ij`."""
    components, count = spec.components, spec.stage_count
    stages = spec.equilibrium_stages()
    inlets = spec.inlets()
    k_stage = {
        j: _k_values(
            provider, DECLARATION_CONTEXT, components, temperatures[j], spec.pressures[j - 1]
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
    `max_j |ΔT_j| ≤ 1e-9 K`, final flows at the stopped `T`, and `x⁰` by §6 steps 5–6."""
    unit = spec.unit_id
    stages = spec.equilibrium_stages()
    rho, phi = stage_ratios(spec, initial, ratio_scale=ratio_scale)
    temperatures = {j: initial.profile[j - 1] + float(profile_shift) for j in stages}
    sweeps, delta = 0, math.inf
    for sweep in range(1, max_sweeps + 1):
        liquid, _ = sweep_flows(spec, provider, temperatures, rho, phi)
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
        if delta <= SWEEP_TOLERANCE:
            sweeps = sweep
            break
    else:
        return CascadeFailure(
            "INITIALIZATION_FAILED",
            f"initialization_failed({PRESOLVE_ID}, sweeps_exhausted)",
            f"{unit}: max |dT| = {delta!r} K after {max_sweeps} sweeps",
        )
    liquid, vapor = sweep_flows(spec, provider, temperatures, rho, phi)
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


# -- spec §7: the solve path ---------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnSolution:
    """Spec §7's answer and §18.2's records: the outcome, the final signature by equilibrium
    stage (top to bottom), the state, the sweeps' start `T⁰` (shifted when asked; A14), the easy
    endpoint with `ρ`, `φ`, sweeps and last `max |ΔT|`, the continued slots with `p⁰`, and the
    `state_sha256` of `x_K`, `x⁰` and the answer."""

    outcome: str
    cause: str
    signature: tuple[Regime, ...]
    state: Mapping[str, float]
    initial: ProfileInitial
    profile: tuple[float, ...]
    endpoint: BubblePointEndpoint
    #: Continued parameter id → `p⁰` (the slot's column at `x⁰`), in stage order.
    continued: Mapping[str, float]
    initial_sha256: str
    endpoint_sha256: str
    result: RegionResult
    recovered_from: RegionResult | None = None
    final_sha256: str | None = None


def continuation(spec: ColumnSpec, profile: Sequence[float]) -> Continuation:
    """Spec §7.5: the continued parameters are exactly the slots §7.3 replaced, each the pinned
    input of a `variable − parameter` row (ADR 0010 D2), in stage order; ratio rows are not."""
    replaced = [slot for slot in slots(spec, profile) if slot.parameter]
    return Continuation(
        type="specification_continuation",
        parameter_ids=tuple(slot.parameter for slot in replaced),
        variable_ids=tuple(slot.variable for slot in replaced),
    )


def recover(
    spec: ColumnSpec,
    profile: Sequence[float],
    target: CompiledCascade,
    provider: PropertyProvider,
    failed: RegionResult,
    policy: SolvePolicy,
    trace: Trace | None = None,
) -> RegionResult:
    """Spec §7.5 (ADR 0010 D3, as S01's `recover`): one recovery solve from the failed solve's
    item-0 opening, its provenance continuing the failed solve's."""
    if failed.opening is None or not failed.branch_provenance:
        raise ValueError(f"defect: {spec.unit_id}'s target ended {failed.outcome} unopened")
    opening_state, opening_regimes = failed.opening
    recovered = run_region(
        target,
        provider,
        opening_state,
        policy,
        initializer_source=PRESOLVE_ID,
        trace=trace,
        recovery=RecoveryStart(
            state=opening_state,
            regimes=opening_regimes,
            continuation=continuation(spec, profile),
            initializer_source=failed.branch_provenance[0]["initializer_source"],
        ),
    )
    return replace(
        recovered,
        branch_provenance=recovered_provenance(
            failed.branch_provenance, recovered.branch_provenance
        ),
        checkpoint=recovered.checkpoint if recovered.checkpoint is not None else failed.checkpoint,
    )


def _as_cascade(spec: ColumnSpec) -> CascadeSpec:
    """A column without ends is S01's cascade under S01's ids (§5 S6 gives it both inlets)."""
    assert spec.top is not None and spec.bottom is not None
    duties = tuple(float(duty) for duty in spec.duties if duty is not None)
    return CascadeSpec(
        unit_id=spec.unit_id,
        stage_count=spec.stage_count,
        pressures=spec.pressures,
        duties=duties,
        top=spec.top,
        bottom=spec.bottom,
        sides=spec.sides,
        components=spec.components,
    )


def solve_target(
    spec: ColumnSpec,
    provider: PropertyProvider,
    target: CompiledCascade,
    x0: Mapping[str, float],
    profile: Sequence[float],
    *,
    policy: SolvePolicy = S02_TARGET_POLICY,
    trace: Trace | None = None,
) -> tuple[RegionResult, RegionResult | None, dict[int, Regime]]:
    """Spec §7 steps 4–5 and §8 from an easy endpoint `x⁰`: the target under `policy`, edge 3
    on its triggers (continuing the slots §7.3 replaced at `profile`), and acceptance of a
    `CONVERGED` answer (`AcceptanceDefectError` on a failure). Returns the final result, the
    failed solve edge 3 recovered from (or `None`), and the final regimes by stage."""
    state = {name: float(x0[name]) for name in target.spec.variable_ids}
    result = run_region(
        target, provider, state, policy, initializer_source=PRESOLVE_ID, trace=trace
    )
    recovered_from: RegionResult | None = None
    if policy.globalization.eo_recovery == "homotopy" and eo_recovery_due(
        result.outcome, result.budget, len(result.attempts)
    ):
        recovered_from = result
        result = recover(spec, profile, target, provider, result, policy, trace)
    regimes = regimes_of(spec, result.attempts[-1].signature) if result.attempts else {}
    if result.outcome == "CONVERGED":
        failures = acceptance_failures(spec, provider, target.spec, result.state, regimes)
        if failures:
            raise AcceptanceDefectError(failures)
    return result, recovered_from, regimes


def solve_column(
    spec: ColumnSpec,
    provider: PropertyProvider,
    *,
    policy: SolvePolicy = S02_TARGET_POLICY,
    profile_shift: float = 0.0,
    ratio_scale: float = 1.0,
    max_sweeps: int = MAX_SWEEPS,
    trace: Trace | None = None,
) -> ColumnSolution | CascadeFailure | DormantAnswer:
    """Spec §7, steps 1–5 (step 3 as §18.2), and §8 on a `CONVERGED` answer.

    `profile_shift` (K) moves the sweeps' start and `ratio_scale` the stage ratios no
    specification holds (spec §18.6 A14); `max_sweeps` is §18.2's cap (A22). A failed endpoint
    returns its typed `CascadeFailure` before any region solve. A `CONVERGED` answer that fails §8
    raises `AcceptanceDefectError`.
    """
    refused = validate(spec, provider, DECLARATION_CONTEXT)
    if refused is not None:
        return refused
    if all(float(a) == 0.0 for inlet in spec.inlets() for a in inlet.state.n):
        # Only a column without ends reaches here (§5 S10): S01 §4.6's closed form.
        return dormant_answer(_as_cascade(spec), provider, DECLARATION_CONTEXT)
    initial = profile_initial(spec, provider, DECLARATION_CONTEXT)
    if isinstance(initial, CascadeFailure):
        return initial
    endpoint = bubble_point_endpoint(
        spec,
        provider,
        initial,
        profile_shift=profile_shift,
        ratio_scale=ratio_scale,
        max_sweeps=max_sweeps,
    )
    if isinstance(endpoint, CascadeFailure):
        return endpoint

    target = compile_column(spec, provider)
    order = target.spec.variable_ids
    x0 = {name: float(endpoint.state[name]) for name in order}
    profile = tuple(t + float(profile_shift) for t in initial.profile)
    replaced = [slot for slot in slots(spec, initial.profile) if slot.parameter]
    continued = {slot.parameter: x0[slot.variable] for slot in replaced}
    result, recovered_from, regimes = solve_target(
        spec, provider, target, x0, initial.profile, policy=policy, trace=trace
    )
    return ColumnSolution(
        outcome=result.outcome,
        cause=result.message if result.outcome != "CONVERGED" else "",
        signature=tuple(regimes.values()),
        state=dict(result.state),
        initial=initial,
        profile=profile,
        endpoint=endpoint,
        continued=continued,
        initial_sha256=state_sha256(dict(initial.state), order),
        endpoint_sha256=state_sha256(x0, order),
        result=result,
        recovered_from=recovered_from,
        final_sha256=state_sha256(dict(result.state), order),
    )


__all__ = [
    "CONTINUED_KIND",
    "FD_COLUMN_SCALE",
    "MAX_SWEEPS",
    "PRESOLVE_EQUATIONS",
    "PRESOLVE_ID",
    "RATIO_LETTER",
    "S02_TARGET_POLICY",
    "SWEEP_TOLERANCE",
    "BubblePointEndpoint",
    "Closure",
    "ColumnSolution",
    "Slot",
    "acceptance_failures",
    "bubble_point_endpoint",
    "closure_types",
    "compile_column",
    "continuation",
    "lifted_splits",
    "model_label",
    "overall_closure",
    "presolve_row_id",
    "presolve_rows",
    "product_columns",
    "products",
    "recover",
    "regimes_of",
    "singular_pairs",
    "slots",
    "solve_column",
    "solve_target",
    "spec_values",
    "split_temperatures",
    "stage_ratios",
    "sweep_flows",
    "system_residuals",
    "zero_flow_forms",
]
