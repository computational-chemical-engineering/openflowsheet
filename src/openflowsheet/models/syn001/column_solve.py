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

and holds a `CONVERGED` answer to §8 before returning it. That is Stage A. S08 adds step 7, Stage B
(S08 design note §5.1, ADR 0048): when Stage A ends in a typed outcome of `REENTRY_OUTCOMES`, or
converges to a state that fails §8 on item 6 alone (a near-trivial split, S08 §3 F4), the
column's initializer builds block openings `V^a 2P^b L^c` from its sources (`column_blocks`) and
solves from each in turn; the first accepted answer is returned, and `ColumnSolution.reentry`
records Stage A and every candidate (§5.6–§5.7).

Each equilibrium stage is one lifted split keyed `<U>.stage.<j>`, as S01's (spec §4.1), PH-type.
The total condenser is not a split (§4.1). The withdrawn Newton profile pre-solve's rows
(`presolve_rows`, §7.3) stay here only as the definition of the registered second easy endpoint
`ref.cases.*.presolve` (A06b); they are not on the solve path.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

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
    TWO_PHASE_SATURATION_TOLERANCE,
    AcceptanceDefectError,
    CompiledCascade,
    run_region,
    saturation_pairs,
)
from openflowsheet.models.syn001.cascade_solve import FD_COLUMN_SCALE as CASCADE_FD_SCALE
from openflowsheet.models.syn001.column import (
    INVERSE_KINDS,
    MODEL_ID,
    PHI_INITIAL,
    RATIO_KINDS,
    ColumnSpec,
    ProfileInitial,
    _initial_state,
    column_warnings,
    component_feeds,
    declared_rows,
    distillate_id,
    distillate_total_id,
    inverse_parameter,
    product_total_id,
    profile_initial,
    purity_reference,
    ratio_parameter,
    reflux_fraction_id,
    reflux_id,
    regime_form,
    slot_column,
    slot_row_id,
    specified_quantity,
    validate,
)
from openflowsheet.models.syn001.equilibrium_form import composition_dependent
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.models.syn001.tp_state import single_phase_admissible
from openflowsheet.orchestrator.execution import Region
from openflowsheet.orchestrator.homotopy import Continuation, HomotopyRecord
from openflowsheet.orchestrator.recovery import (
    eo_recovery_due,
    recovered_provenance,
    solver_outcomes,
)
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
from openflowsheet.orchestrator.trace import SolvePolicy, Trace, fraction_string
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

if TYPE_CHECKING:
    # `column_blocks` imports this module; Stage B imports it at call time (`_stage_b`).
    from openflowsheet.models.syn001.column_blocks import BlockEndpoint

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

#: `ref.cases.*.continued`'s kind letter of each continued slot (S06 §12: an inverse slot's is
#: `T`, `N` or `U`, the letter of the column it pins).
CONTINUED_KIND: Final[Mapping[str, str]] = {
    "duty": "Q",
    "distillate_rate": "D",
    "bottoms_rate": "B",
    "temperature": "T",
    "recovery": "N",
    "purity": "U",
}

#: S06 §8 item 4: the binary64 slack on a recovery's and a purity's bound, `2⁻⁵²`.
QUOTIENT_SLACK: Final = 2.0**-52

#: The prefix of every item-6 failure string of `acceptance_failures`.
ITEM_6_PREFIX: Final = "§8.6: "

#: S08 §5.1 trigger (i): the typed region outcomes of Stage A that start Stage B, `T_B`.
REENTRY_OUTCOMES: Final = frozenset(
    {
        "HOMOTOPY_STALLED",
        "ACTIVE_SET_CYCLING",
        "ATTEMPTS_EXHAUSTED",
        "LINE_SEARCH_FAILED",
        "LINEAR_SOLVE_FAILED",
        "BOUND_BLOCKED",
        "STAGNATION",
        "PTC_STALLED",
        "EVALUATION_ERROR",
    }
)
#: S08 §5.1 trigger (i): `BUDGET_EXHAUSTED` starts Stage B only on these budgets (never on
#: `property_calls`).
REENTRY_BUDGETS: Final = frozenset({"newton_iterations", "ptc_steps"})
#: S08 §5.1 trigger (ii) and §5.4: the code of a `CONVERGED` state that fails §8 on item 6 alone.
NEAR_TRIVIAL_SPLIT: Final = "near_trivial_split"

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


# -- spec §7: the solve path ---------------------------------------------------------------------


@dataclass(frozen=True)
class StageARecord:
    """S08 §5.6: Stage A's answer when it started Stage B — its outcome and cause (on trigger
    (ii) `CONVERGED` with cause `near_trivial_split(<stages>)`), its region results, the
    `state_sha256` of its endpoint `x⁰` and of its final state, and its item-6 failure strings
    (`()` on a typed outcome)."""

    outcome: str
    cause: str
    result: RegionResult
    recovered_from: RegionResult | None
    endpoint_sha256: str
    final_sha256: str | None
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateRecord:
    """S08 §5.6: one Stage-B candidate `(a, c)` — its signature `σ(a, c)` over the equilibrium
    stages, `endpoint` `"built"` or the refusal's cause (then nothing was solved: every later
    field is `None` and `cause` is the refusal's), the endpoint's `state_sha256`, and the solve's
    outcome, cause (`""` when accepted; the region's message, `near_trivial_split(<stages>)` or
    `unsupported(…)` otherwise) and region results."""

    a: int
    c: int
    signature: tuple[Regime, ...]
    endpoint: str
    endpoint_sha256: str | None
    outcome: str | None
    cause: str
    result: RegionResult | None
    recovered_from: RegionResult | None


@dataclass(frozen=True)
class BlockReentry:
    """S08 §5.6: Stage B's record — its trigger (Stage A's outcome, or `near_trivial_split`),
    Stage A, every candidate tried in §5.2's order, and the index of the accepted one (`None`
    when none was accepted)."""

    trigger: str
    stage_a: StageARecord
    candidates: tuple[CandidateRecord, ...]
    accepted: int | None


@dataclass(frozen=True)
class ColumnSolution:
    """Spec §7's answer and §18.2's records: the outcome, the final signature by equilibrium
    stage (top to bottom), the state, the sweeps' start `T⁰` (shifted when asked; A14), the easy
    endpoint with `ρ`, `φ`, sweeps and last `max |ΔT|`, the continued slots with `p⁰`, and the
    `state_sha256` of `x_K`, `x⁰` and the answer.

    S08 §5.6: the top-level fields always describe the returned solve. When a Stage-B candidate is
    accepted they are that candidate's (`endpoint` is then its `BlockEndpoint`); otherwise they
    are Stage A's. `reentry` is `None` whenever Stage B did not run."""

    outcome: str
    cause: str
    signature: tuple[Regime, ...]
    state: Mapping[str, float]
    initial: ProfileInitial
    profile: tuple[float, ...]
    endpoint: BubblePointEndpoint | BlockEndpoint
    #: Continued parameter id → `p⁰` (the slot's column at `x⁰`), in stage order.
    continued: Mapping[str, float]
    initial_sha256: str
    endpoint_sha256: str
    result: RegionResult
    recovered_from: RegionResult | None = None
    final_sha256: str | None = None
    #: C8: stable `code(detail)` notices (`column_warnings`); not part of any `state_sha256`.
    warnings: tuple[str, ...] = ()
    #: S06 §7.5: one record per inverse end, condenser first.
    inverse: tuple[InverseRecord, ...] = ()
    #: S06 §7.3: per inverse end on a non-`CONVERGED` answer; empty on a `CONVERGED` one.
    unreached: tuple[UnreachedSpecification, ...] = ()
    #: S08 §5.6: Stage B's record; not part of any `state_sha256`.
    reentry: BlockReentry | None = None


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


def target_attempt(
    spec: ColumnSpec,
    provider: PropertyProvider,
    target: CompiledCascade,
    x0: Mapping[str, float],
    profile: Sequence[float],
    *,
    policy: SolvePolicy = S02_TARGET_POLICY,
    trace: Trace | None = None,
    initializer_source: str = PRESOLVE_ID,
) -> tuple[RegionResult, RegionResult | None, dict[int, Regime], tuple[str, ...], int | None]:
    """Spec §7 steps 4–5 and §8 from an easy endpoint `x⁰` whose id is `initializer_source`
    (S08 §5.1): the target under `policy`, edge 3 on its triggers (continuing the slots §7.3
    replaced at `profile`), and §8 evaluated on a `CONVERGED` answer, without raising. Returns
    the final result, the failed solve edge 3 recovered from (or `None`), the final regimes by
    stage, §8's failures and S06 §8 item 3's single-phase `temperature`-specified stage (or
    `None`); the last two are empty and `None` unless the answer is `CONVERGED`."""
    state = {name: float(x0[name]) for name in target.spec.variable_ids}
    result = run_region(
        target, provider, state, policy, initializer_source=initializer_source, trace=trace
    )
    recovered_from: RegionResult | None = None
    if policy.globalization.eo_recovery == "homotopy" and eo_recovery_due(
        result.outcome, result.budget, attempts=solver_outcomes(result.attempts)
    ):
        recovered_from = result
        result = recover(spec, profile, target, provider, result, policy, trace)
    regimes = regimes_of(spec, result.attempts[-1].signature) if result.attempts else {}
    failures: tuple[str, ...] = ()
    unsupported: int | None = None
    if result.outcome == "CONVERGED":
        failures = acceptance_failures(spec, provider, target.spec, result.state, regimes)
        unsupported = single_phase_specified_stage(spec, regimes)
    return result, recovered_from, regimes, failures, unsupported


def _unsupported(
    spec: ColumnSpec, regimes: Mapping[int, Regime], stage: int
) -> UnsupportedAnswerError:
    """S06 §8 item 3's answer for a single-phase `temperature`-specified `stage`."""
    return UnsupportedAnswerError(
        f"unsupported(temperature_specification_on_single_phase_stage:{stage})",
        f"{spec.unit_id} stage {stage} is {regimes[stage]} at the CONVERGED state",
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
    initializer_source: str = PRESOLVE_ID,
) -> tuple[RegionResult, RegionResult | None, dict[int, Regime]]:
    """Spec §7 steps 4–5 and §8 from an easy endpoint `x⁰`: `target_attempt`, and acceptance of
    a `CONVERGED` answer (`AcceptanceDefectError` on a failure). S06 §8 item 3 is decided after
    the defect clauses (S06 §17.3, R-610): a defect-free `CONVERGED` answer whose
    `temperature`-specified stage is single-phase raises `UnsupportedAnswerError` (never a
    success, and not a defect); a defective one is a defect whatever the regime. Returns the
    final result, the failed solve edge 3 recovered from (or `None`), and the final regimes by
    stage."""
    result, recovered_from, regimes, failures, unsupported = target_attempt(
        spec,
        provider,
        target,
        x0,
        profile,
        policy=policy,
        trace=trace,
        initializer_source=initializer_source,
    )
    if failures:
        raise AcceptanceDefectError(failures)
    if unsupported is not None:
        raise _unsupported(spec, regimes, unsupported)
    return result, recovered_from, regimes


def _item_6_stages(
    spec: ColumnSpec,
    provider: PropertyProvider,
    state: Mapping[str, float],
    regimes: Mapping[int, Regime],
    failures: Sequence[str],
) -> tuple[int, ...]:
    """The `TWO_PHASE` stages that fail item 6, top to bottom, when §8's `failures` are all item
    6's; `()` when there is none or another item failed as well."""
    if not failures or not all(failure.startswith(ITEM_6_PREFIX) for failure in failures):
        return ()
    errors = saturation_errors(spec, provider, state, regimes)
    return tuple(
        stage for stage, error in errors.items() if not error <= TWO_PHASE_SATURATION_TOLERANCE
    )


def _near_trivial_cause(stages: Sequence[int]) -> str:
    return f"{NEAR_TRIVIAL_SPLIT}({','.join(str(stage) for stage in stages)})"


def reentry_trigger(result: RegionResult, near_trivial: Sequence[int]) -> str | None:
    """S08 §5.1: Stage B's trigger on Stage A's final `result` — its outcome when that is in
    `REENTRY_OUTCOMES`, or `BUDGET_EXHAUSTED` on a budget of `REENTRY_BUDGETS` (trigger (i));
    `near_trivial_split` when it is `CONVERGED` and fails §8 on item 6 alone, at the stages
    `near_trivial` (trigger (ii)); `None` otherwise."""
    if result.outcome == "CONVERGED":
        return NEAR_TRIVIAL_SPLIT if near_trivial else None
    if result.outcome in REENTRY_OUTCOMES:
        return result.outcome
    if result.outcome == "BUDGET_EXHAUSTED" and result.budget in REENTRY_BUDGETS:
        return result.outcome
    return None


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
    """Spec §7, steps 1–5 (step 3 as §18.2), and §8 on a `CONVERGED` answer (Stage A); then S08's
    step 7 (Stage B, §5.1) on its trigger.

    `profile_shift` (K) moves the sweeps' start and `ratio_scale` the stage ratios no
    specification holds (spec §18.6 A14); `max_sweeps` is §18.2's cap (A22). A failed endpoint
    returns its typed `CascadeFailure` before any region solve. A `CONVERGED` answer that fails §8
    raises `AcceptanceDefectError`, unless it fails item 6 alone (S08 §5.1 trigger (ii)); one S06
    §8 item 3 does not offer is the `CascadeFailure` `CAPABILITY_UNAVAILABLE` with its cause.
    S06: `inverse` holds §7.5's records and `unreached` §7.3's report. S08: Stage B's first
    accepted candidate is the answer; when none is accepted a typed Stage-A answer is returned
    with `reentry`, and an item-6 rejection raises `AcceptanceDefectError` (§5.7).

    C8: every `ColumnSolution` and `CascadeFailure` for a duty-only specification carries
    `column_warnings(spec)`; the dormant answer has no ends and none.
    """
    warnings = column_warnings(spec)
    refused = validate(spec, provider, DECLARATION_CONTEXT)
    if refused is not None:
        return replace(refused, warnings=warnings)
    if all(float(a) == 0.0 for inlet in spec.inlets() for a in inlet.state.n):
        # Only a column without ends reaches here (§5 S10): S01 §4.6's closed form.
        return dormant_answer(_as_cascade(spec), provider, DECLARATION_CONTEXT)
    initial = profile_initial(spec, provider, DECLARATION_CONTEXT)
    if isinstance(initial, CascadeFailure):
        return replace(initial, warnings=warnings)
    endpoint = bubble_point_endpoint(
        spec,
        provider,
        initial,
        profile_shift=profile_shift,
        ratio_scale=ratio_scale,
        max_sweeps=max_sweeps,
    )
    if isinstance(endpoint, CascadeFailure):
        return replace(endpoint, warnings=warnings)

    target = compile_column(spec, provider)
    order = target.spec.variable_ids
    x0 = {name: float(endpoint.state[name]) for name in order}
    profile = tuple(t + float(profile_shift) for t in initial.profile)
    result, recovered_from, regimes, failures, unsupported = target_attempt(
        spec, provider, target, x0, initial.profile, policy=policy, trace=trace
    )
    near_trivial = _item_6_stages(spec, provider, result.state, regimes, failures)
    trigger = reentry_trigger(result, near_trivial)
    if failures and trigger is None:
        raise AcceptanceDefectError(failures)
    if not failures and unsupported is not None:
        scope = _unsupported(spec, regimes, unsupported)
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE", scope.cause, scope.detail, warnings=warnings
        )
    answer = _column_answer(
        spec, initial, profile, endpoint, target, x0, result, recovered_from, regimes, warnings
    )
    if trigger is None:
        return answer
    stage_a = StageARecord(
        outcome=answer.outcome,
        cause=_near_trivial_cause(near_trivial) if failures else answer.cause,
        result=result,
        recovered_from=recovered_from,
        endpoint_sha256=answer.endpoint_sha256,
        final_sha256=answer.final_sha256,
        failures=failures,
    )
    return _stage_b(
        spec,
        provider,
        target,
        initial,
        answer,
        BlockReentry(trigger, stage_a, (), None),
        policy=policy,
        profile_shift=profile_shift,
        ratio_scale=ratio_scale,
        max_sweeps=max_sweeps,
        trace=trace,
    )


def _column_answer(
    spec: ColumnSpec,
    initial: ProfileInitial,
    profile: tuple[float, ...],
    endpoint: BubblePointEndpoint | BlockEndpoint,
    target: CompiledCascade,
    x0: Mapping[str, float],
    result: RegionResult,
    recovered_from: RegionResult | None,
    regimes: Mapping[int, Regime],
    warnings: tuple[str, ...],
) -> ColumnSolution:
    """The `ColumnSolution` of one solve from the endpoint `x⁰` (Stage A's, or a Stage-B
    candidate's: S08 §5.6's top-level fields)."""
    order = target.spec.variable_ids
    replaced = [slot for slot in slots(spec, initial.profile) if slot.parameter]
    return ColumnSolution(
        outcome=result.outcome,
        cause=result.message if result.outcome != "CONVERGED" else "",
        signature=tuple(regimes.values()),
        state=dict(result.state),
        initial=initial,
        profile=profile,
        endpoint=endpoint,
        continued={slot.parameter: x0[slot.variable] for slot in replaced},
        initial_sha256=state_sha256(dict(initial.state), order),
        endpoint_sha256=state_sha256(x0, order),
        result=result,
        recovered_from=recovered_from,
        final_sha256=state_sha256(dict(result.state), order),
        warnings=warnings,
        inverse=inverse_records(spec, x0),
        unreached=unreached_specifications(spec, result, recovered_from),
    )


def _stage_b(
    spec: ColumnSpec,
    provider: PropertyProvider,
    target: CompiledCascade,
    initial: ProfileInitial,
    answer: ColumnSolution,
    reentry: BlockReentry,
    *,
    policy: SolvePolicy,
    profile_shift: float,
    ratio_scale: float,
    max_sweeps: int,
    trace: Trace | None,
) -> ColumnSolution:
    """S08 §5.1 Stage B and §5.7 after Stage A's `answer` triggered it: for each candidate of
    §5.2, in order, its §5.3 endpoint (a refusal is recorded and the next candidate tried), then
    §5.4's solve from it under the same policy; the first accepted answer is returned with
    `reentry`. None accepted: Stage A's typed `answer` with `reentry`, or, when Stage A failed
    item 6, `AcceptanceDefectError` with Stage A's failures. A candidate's §8 failure other than
    item 6 is a defect and raises."""
    from openflowsheet.models.syn001 import column_blocks

    order = target.spec.variable_ids
    records: list[CandidateRecord] = []
    for index, candidate in enumerate(column_blocks.candidates(spec)):
        a, c = candidate
        signature = column_blocks.block_signature(spec, candidate)
        built = column_blocks.block_endpoint(
            spec,
            provider,
            initial,
            candidate,
            profile_shift=profile_shift,
            ratio_scale=ratio_scale,
            max_sweeps=max_sweeps,
        )
        if isinstance(built, CascadeFailure):
            records.append(
                CandidateRecord(a, c, signature, built.cause, None, None, built.cause, None, None)
            )
            continue
        x0 = {name: float(built.state[name]) for name in order}
        result, recovered_from, regimes, failures, unsupported = target_attempt(
            spec,
            provider,
            target,
            x0,
            initial.profile,
            policy=policy,
            trace=trace,
            initializer_source=column_blocks.BLOCK_ENDPOINT_ID,
        )
        cause = result.message if result.outcome != "CONVERGED" else ""
        if failures:
            near_trivial = _item_6_stages(spec, provider, result.state, regimes, failures)
            if not near_trivial:
                raise AcceptanceDefectError(failures)
            cause = _near_trivial_cause(near_trivial)
        elif result.outcome == "CONVERGED" and unsupported is not None:
            cause = _unsupported(spec, regimes, unsupported).cause
        records.append(
            CandidateRecord(
                a,
                c,
                signature,
                "built",
                state_sha256(x0, order),
                result.outcome,
                cause,
                result,
                recovered_from,
            )
        )
        if result.outcome == "CONVERGED" and not cause:
            accepted = _column_answer(
                spec,
                initial,
                answer.profile,
                built,
                target,
                x0,
                result,
                recovered_from,
                regimes,
                answer.warnings,
            )
            return replace(
                accepted, reentry=replace(reentry, candidates=tuple(records), accepted=index)
            )
    reentry = replace(reentry, candidates=tuple(records))
    if reentry.stage_a.failures:
        refused = AcceptanceDefectError(reentry.stage_a.failures)
        tried = "; ".join(f"({r.a}, {r.c}) {r.cause}" for r in records) or "none"
        refused.add_note(f"S08 §5.7: no Stage-B candidate was accepted; tried: {tried}")
        raise refused
    return replace(answer, reentry=reentry)


__all__ = [
    "CONTINUED_KIND",
    "FD_COLUMN_SCALE",
    "MAX_SWEEPS",
    "PRESOLVE_EQUATIONS",
    "PRESOLVE_ID",
    "QUOTIENT_SLACK",
    "ITEM_6_PREFIX",
    "NEAR_TRIVIAL_SPLIT",
    "RATIO_LETTER",
    "REENTRY_BUDGETS",
    "REENTRY_OUTCOMES",
    "S02_TARGET_POLICY",
    "SWEEP_COMPOSITION_TOLERANCE",
    "SWEEP_RELAXATION",
    "SWEEP_TOLERANCE",
    "BlockReentry",
    "BubblePointEndpoint",
    "CandidateRecord",
    "Closure",
    "ColumnSolution",
    "InverseRecord",
    "Slot",
    "StageARecord",
    "UnreachedSpecification",
    "UnsupportedAnswerError",
    "acceptance_failures",
    "bubble_point_endpoint",
    "closure_types",
    "compile_column",
    "continuation",
    "inverse_ends",
    "inverse_records",
    "lambda_state",
    "lifted_splits",
    "model_label",
    "overall_closure",
    "presolve_row_id",
    "presolve_rows",
    "product_columns",
    "products",
    "recover",
    "reentry_trigger",
    "regimes_of",
    "single_phase_specified_stage",
    "singular_pairs",
    "slots",
    "solve_column",
    "solve_target",
    "spec_values",
    "split_temperatures",
    "stage_ratios",
    "sweep_flows",
    "system_residuals",
    "target_attempt",
    "target_bound",
    "unreached_specifications",
    "zero_flow_forms",
]
