"""`syn001.column` compiled: S02 spec §7.3's slot substitutions, §4.1's per-stage region descriptors
and the compiled problem.

Moved verbatim from `column_solve` (S19 B3), which re-exports every name here and keeps the solve
path. This module imports nothing from `column_solve`, `column_blocks` or the other column modules
that solve.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.spec import EquationSpec, QuantityKind
from openflowsheet.models import Contribution, SpecificationError, origin
from openflowsheet.models.rows import ratio_row, specification_row
from openflowsheet.models.syn001.cascade import (
    _parameter,
    declared_problem,
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
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT, CompiledCascade
from openflowsheet.models.syn001.column import (
    MODEL_ID,
    RATIO_KINDS,
    ColumnSpec,
    declared_rows,
    distillate_total_id,
    ratio_parameter,
    reflux_id,
    regime_form,
    slot_column,
    slot_row_id,
)
from openflowsheet.orchestrator.execution import Region
from openflowsheet.orchestrator.region import ClosureType, LiftedSplit, ZeroFlowForm
from openflowsheet.thermo import PropertyProvider

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
