"""`syn001.column` compiled and solved: S02 spec §7 and §8 (WO-2).

`column.py` holds the unit layer (WO-1): the specification, its §5 refusals, the §2 rows, the
regime forms and the §6 initializer. This module compiles those rows and runs spec §7's path on
them, calling `orchestrator.region.solve_region` unchanged, through S01's `run_region`:

1. validate (§5); an all-dormant column (possible only without ends, §5 S10) is S01 §4.6's;
2. initialize (`s02-profile-cmo-v1`), giving `x_K`;
3. the profile pre-solve `s02-profile-presolve-v1`: the target's columns with every
   `variable − parameter` slot row of an equilibrium stage replaced by `T_j − T_j⁰`, such a slot
   of a total condenser by `Σ r − 1·D`, and every ratio slot row kept at its target; one attempt
   from `x_K`, which must converge with every equilibrium stage `TWO_PHASE`; its root is `x⁰`;
4. the target from `x⁰` under S01's registered `s01-default-v1` (no new policy, spec §0);
5. recovery edge 3 (ADR 0010 D3) on its triggers, continuing exactly the replaced slots from
   `p⁰` = their columns at the opening;

and holds a `CONVERGED` answer to §8 before returning it.

Each equilibrium stage is one lifted split keyed `<U>.stage.<j>`, as S01's (spec §4.1): PH-type in
the target, TP-type in the pre-solve (S01 §17.10's rule, which §7.3 adopts). The total condenser
is not a split (§4.1).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

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
from openflowsheet.models.syn001.cascade_solve import PRESOLVE_POLICY as S01_PRESOLVE_POLICY
from openflowsheet.models.syn001.column import (
    MODEL_ID,
    RATIO_KINDS,
    ColumnSpec,
    ProfileInitial,
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

#: Spec §7.3's registered pre-solve.
PRESOLVE_ID: Final = "s02-profile-presolve-v1"

#: Spec §7.3 ("S01 §7.3 with T̄ replaced by the profile"): S01's pre-solve policy — one attempt,
#: no recovery edge, otherwise `s01-default-v1` — under this pre-solve's id. Derived from S01's
#: registered object, so its phase contract is S01's registered v2 (spec §0; T05b B06).
PRESOLVE_POLICY: Final[SolvePolicy] = replace(S01_PRESOLVE_POLICY, policy_id=PRESOLVE_ID)

#: Spec §7.4: the target's policy is S01's registered `s01-default-v1`, reused (spec §0).
S02_TARGET_POLICY: Final[SolvePolicy] = S01_DEFAULT_V1

#: The pre-solve's replacement rows `T_j − T_j⁰` (spec §7.3). A total condenser's replacement
#: `Σ r − 1·D` is the `COL-reflux-ratio` row at `RR = 1` and needs no declaration of its own.
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

Problem = Literal["target", "presolve"]


# -- spec §7.3: the slot substitutions -----------------------------------------------------------


@dataclass(frozen=True)
class Slot:
    """One stage's slot row in the pre-solve (spec §7.3, §7.6's records).

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
    """Spec §7.3: the declared rows with every replaced slot row replaced in place. Same
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


def closure_types(spec: ColumnSpec, problem: Problem) -> dict[str, ClosureType]:
    """PH for every equilibrium stage of the target, TP in the pre-solve (S01's rule)."""
    kind: ClosureType = "PH" if problem == "target" else "TP"
    return {stage_unit(spec.unit_id, j): kind for j in spec.equilibrium_stages()}


def split_temperatures(spec: ColumnSpec) -> dict[str, tuple[str, ...]]:
    return {
        stage_unit(spec.unit_id, j): (stage_temperature_id(spec.unit_id, j),)
        for j in spec.equilibrium_stages()
    }


# -- compile -------------------------------------------------------------------------------------


def model_label(provider: PropertyProvider, problem: Problem) -> str:
    """ADR 0002 D2.7, as S01's: the equation set and the property package."""
    capabilities = provider.describe()
    tag = "S02-column" if problem == "target" else "S02-column-pre"
    label = (
        f"{tag}-{capabilities.provider_id}"
        f"-{capabilities.implementation_sha256[:12]}-{capabilities.data_sha256[:12]}"
    )
    if len(label) > 64:
        raise SpecificationError(f"the label {label!r} exceeds ADR 0002's 64 characters")
    return label


def compile_column(
    spec: ColumnSpec,
    provider: PropertyProvider,
    problem: Problem = "target",
    *,
    profile: Sequence[float] | None = None,
) -> CompiledCascade:
    """The target's (or, with `profile`, the pre-solve's) `ProblemSpec`, compiled, and its
    region: every declared row over every declared column."""
    rows = declared_rows(spec, provider, DECLARATION_CONTEXT)
    if problem == "presolve":
        if profile is None:
            raise ValueError("the pre-solve's rows need the profile T⁰")
        rows = presolve_rows(rows, spec, profile)
    declared = declared_problem(rows, model_label(provider, problem))
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
        problem=problem,
        spec=declared,
        compiled=compile_problem(declared),
        region=region,
        splits=splits,
        forms=zero_flow_forms(spec),
        types=closure_types(spec, problem),
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


# -- spec §7: the solve path ---------------------------------------------------------------------


@dataclass(frozen=True)
class PresolveSummary:
    """Spec §7.6: the pre-solve's attempt as recorded and its root's `state_sha256`."""

    outcome: str
    solver_outcome: str | None
    iterations: int
    signature: tuple[Regime, ...]
    state_sha256: str


@dataclass(frozen=True)
class ColumnSolution:
    """Spec §7's answer and §7.6's records: the outcome, the final signature by equilibrium
    stage (top to bottom), the state, the profile `T⁰`, the slot substitutions and the
    continued slots with `p⁰`."""

    outcome: str
    cause: str
    signature: tuple[Regime, ...]
    state: Mapping[str, float]
    initial: ProfileInitial
    #: The pre-solve's profile level (`initial.profile`, shifted when asked; A14).
    profile: tuple[float, ...]
    slots: tuple[Slot, ...]
    #: Continued parameter id → `p⁰` (the slot's column at `x⁰`); empty when the pre-solve failed.
    continued: Mapping[str, float]
    initial_sha256: str
    opening_sha256: str
    presolve_sha256: str | None
    presolve: RegionResult
    presolve_summary: PresolveSummary
    result: RegionResult | None
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
    """Spec §7 steps 4–5 and §8 from a pre-solve root `x⁰`: the target under `policy`, edge 3
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
    opening: Mapping[str, float] | None = None,
    profile_shift: float = 0.0,
    trace: Trace | None = None,
) -> ColumnSolution | CascadeFailure | DormantAnswer:
    """Spec §7, steps 1–5, and §8 on a `CONVERGED` answer.

    `opening` replaces `x_K` as the pre-solve's start and `profile_shift` (K) moves the
    pre-solve's profile level (spec §10 A14, R-517's reading). A `CONVERGED` answer that fails §8
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

    target = compile_column(spec, provider)
    order = target.spec.variable_ids
    start = dict(initial.state) if opening is None else {n: float(opening[n]) for n in order}
    initial_sha = state_sha256(dict(initial.state), order)
    opening_sha = state_sha256(start, order)

    profile = tuple(t + float(profile_shift) for t in initial.profile)
    substitutions = slots(spec, profile)
    pre = compile_column(spec, provider, "presolve", profile=profile)
    presolve = run_region(
        pre, provider, start, PRESOLVE_POLICY, initializer_source=initial.initializer
    )
    final_attempt = presolve.attempts[-1] if presolve.attempts else None
    pre_regimes = tuple(regimes_of(spec, final_attempt.signature).values()) if final_attempt else ()
    summary = PresolveSummary(
        outcome=presolve.outcome,
        solver_outcome=None if final_attempt is None else final_attempt.solver_outcome,
        iterations=presolve.iterations,
        signature=pre_regimes,
        state_sha256=state_sha256(dict(presolve.state), order),
    )
    two_phase = bool(pre_regimes) and all(r == "TWO_PHASE" for r in pre_regimes)
    if presolve.outcome != "CONVERGED" or not two_phase:
        outcome = presolve.outcome if presolve.outcome != "CONVERGED" else "not_two_phase"
        return ColumnSolution(
            outcome="INITIALIZATION_FAILED",
            cause=f"initialization_failed({PRESOLVE_ID}, {outcome})",
            signature=(),
            state=dict(presolve.state),
            initial=initial,
            profile=profile,
            slots=substitutions,
            continued={},
            initial_sha256=initial_sha,
            opening_sha256=opening_sha,
            presolve_sha256=None,
            presolve=presolve,
            presolve_summary=summary,
            result=None,
        )
    x0 = {name: float(presolve.state[name]) for name in order}
    continued = {slot.parameter: x0[slot.variable] for slot in substitutions if slot.parameter}
    result, recovered_from, regimes = solve_target(
        spec, provider, target, x0, profile, policy=policy, trace=trace
    )
    return ColumnSolution(
        outcome=result.outcome,
        cause=result.message if result.outcome != "CONVERGED" else "",
        signature=tuple(regimes.values()),
        state=dict(result.state),
        initial=initial,
        profile=profile,
        slots=substitutions,
        continued=continued,
        initial_sha256=initial_sha,
        opening_sha256=opening_sha,
        presolve_sha256=summary.state_sha256,
        presolve=presolve,
        presolve_summary=summary,
        result=result,
        recovered_from=recovered_from,
        final_sha256=state_sha256(dict(result.state), order),
    )


__all__ = [
    "CONTINUED_KIND",
    "FD_COLUMN_SCALE",
    "PRESOLVE_EQUATIONS",
    "PRESOLVE_ID",
    "PRESOLVE_POLICY",
    "RATIO_LETTER",
    "S02_TARGET_POLICY",
    "Closure",
    "ColumnSolution",
    "PresolveSummary",
    "Slot",
    "acceptance_failures",
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
    "system_residuals",
    "zero_flow_forms",
]
