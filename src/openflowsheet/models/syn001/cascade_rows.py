"""`syn001.cascade`'s declared rows: S01 spec §2's stage and inlet rows built from `models.rows`,
and the declared problem.

Moved verbatim from `cascade` (S19 B4), which re-exports every name here and keeps the §5
refusals, the §4.2 regime forms and the §4.6 dormant answer. This module imports only
`cascade_spec` among the cascade modules.
"""

from __future__ import annotations

from collections.abc import Callable

from openflowsheet.canonical import normalize_zero
from openflowsheet.compile.spec import EquationSpec, ProblemSpec, QuantityKind, RowBuilder
from openflowsheet.compiled import EvaluationContext, RowAccumulation
from openflowsheet.models import (
    Contribution,
    SpecificationError,
    flow_id,
    origin,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.rows import (
    balance_row,
    definition_row,
    energy_row,
    equilibrium_row,
    specification_row,
)
from openflowsheet.models.syn001.blocks import EnthalpyFlowBlock, LnKBlock
from openflowsheet.models.syn001.cascade_spec import (
    _TOKEN,
    BOTTOM,
    MODEL_ID,
    TOP,
    CascadeSpec,
    PlacedInlet,
    _parameter,
    _phase,
    energy_row_id,
    inlet_row_id,
    inlet_stream,
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_duty_id,
    stage_pressure_id,
    stage_row_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.tp_state import enthalpy_block_id, lnk_block_id
from openflowsheet.thermo import Phase, PropertyProvider

# -- spec §2: declared rows ----------------------------------------------------------------------


def _token(text: str) -> str:
    if not _TOKEN.match(text):
        raise SpecificationError(
            f"{text!r} cannot name a property block: a letter followed by letters, digits and "
            "non-consecutive underscores"
        )
    return text


def declared_rows(
    spec: CascadeSpec, provider: PropertyProvider, context: EvaluationContext
) -> Contribution:
    """The §2 columns, rows, blocks and pinned inputs: `14N + (C + 2) n_in` of each.

    The cascade owns every column it declares (stage and inlet), so all of them are in
    `variable_ids`. Stage j's columns come first, in stage order, then each inlet's. Call after
    `validate`.
    """
    unit, components = _token(spec.unit_id), spec.components
    count = spec.stage_count
    inlets = spec.inlets()
    for inlet in inlets:
        _token(inlet.port)

    variables: list[str] = []
    variable_kinds: dict[str, QuantityKind] = {}
    equations: list[EquationSpec] = []
    row_kinds: dict[str, QuantityKind] = {}
    blocks: list[LnKBlock | EnthalpyFlowBlock] = []
    block_inputs: dict[str, tuple[str, ...]] = {}
    parameter_ids: list[str] = []
    parameters: dict[str, float] = {}

    def column(name: str, kind: QuantityKind) -> None:
        variables.append(name)
        variable_kinds[name] = kind

    def row(
        equation_id: str,
        build: RowBuilder,
        accumulation: RowAccumulation,
        family: str,
        kind: QuantityKind,
    ) -> None:
        equations.append(
            EquationSpec(
                equation_id=equation_id,
                build=build,
                accumulation=accumulation,
                origin=origin(MODEL_ID, family),
            )
        )
        row_kinds[equation_id] = kind

    def pin(name: str, value: float) -> str:
        parameter = _parameter(name)
        parameter_ids.append(parameter)
        parameters[parameter] = normalize_zero(float(value))
        return parameter

    # Enthalpy blocks: one per (stage, phase) outlet and one per inlet. Each internal stream has
    # one block, read with + by the stage it enters and with - by the stage it leaves, so the
    # overall energy closure of spec §2 cancels term by term.
    vapor_keys: dict[int, tuple[str, ...]] = {}
    liquid_keys: dict[int, tuple[str, ...]] = {}
    lnk_keys: dict[int, str] = {}
    for stage in range(1, count + 1):
        token = f"{unit}_s{stage}"
        lnk = LnKBlock(provider, components, context, block_id=lnk_block_id(token))
        blocks.append(lnk)
        block_inputs[lnk.block_id] = (
            stage_temperature_id(unit, stage),
            stage_pressure_id(unit, stage),
        )
        lnk_keys[stage] = lnk.block_id
        outlets: tuple[
            tuple[Phase, Callable[[str, int, str], str], dict[int, tuple[str, ...]]], ...
        ]
        outlets = (("VAPOR", vapor_id, vapor_keys), ("LIQUID", liquid_id, liquid_keys))
        for phase, flows, keys in outlets:
            block = EnthalpyFlowBlock(
                provider, components, phase, context, block_id=enthalpy_block_id(token, phase)
            )
            blocks.append(block)
            block_inputs[block.block_id] = (
                *(flows(unit, stage, c) for c in components),
                stage_temperature_id(unit, stage),
                stage_pressure_id(unit, stage),
            )
            keys[stage] = tuple(f"{block.block_id}.{out}" for out in block.output_ids)
    inlet_keys: dict[str, tuple[str, ...]] = {}
    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        phase = _phase(inlet.state)
        block = EnthalpyFlowBlock(
            provider,
            components,
            phase,
            context,
            block_id=enthalpy_block_id(f"{unit}_in_{inlet.port}", phase),
        )
        blocks.append(block)
        block_inputs[block.block_id] = (
            *(flow_id(stream, c) for c in components),
            temperature_id(stream),
            pressure_id(stream),
        )
        inlet_keys[inlet.port] = tuple(f"{block.block_id}.{out}" for out in block.output_ids)

    sides_at: dict[int, list[PlacedInlet]] = {}
    for inlet in inlets[2:]:
        sides_at.setdefault(inlet.stage, []).append(inlet)

    for stage in range(1, count + 1):
        for c in components:
            column(liquid_id(unit, stage, c), "molar_flow")
        for c in components:
            column(vapor_id(unit, stage, c), "molar_flow")
        for c in components:
            column(mixed_id(unit, stage, c), "molar_flow")
        column(liquid_total_id(unit, stage), "molar_flow")
        column(vapor_total_id(unit, stage), "molar_flow")
        column(stage_temperature_id(unit, stage), "temperature")
        column(stage_pressure_id(unit, stage), "pressure")
        column(stage_duty_id(unit, stage), "heat_rate")

        sides = sides_at.get(stage, [])
        for c in components:
            above = (
                flow_id(inlet_stream(unit, TOP), c) if stage == 1 else liquid_id(unit, stage - 1, c)
            )
            below = (
                flow_id(inlet_stream(unit, BOTTOM), c)
                if stage == count
                else vapor_id(unit, stage + 1, c)
            )
            inflow = (above, below, *(flow_id(inlet_stream(unit, s.port), c) for s in sides))
            row(
                stage_row_id(unit, stage, "mix", c),
                balance_row(inflow, (mixed_id(unit, stage, c),)),
                "algebraic",
                "CAS-mix",
                "molar_flow",
            )
        for c in components:
            row(
                stage_row_id(unit, stage, "mole", c),
                balance_row(
                    (mixed_id(unit, stage, c),),
                    (vapor_id(unit, stage, c), liquid_id(unit, stage, c)),
                ),
                "holdup_balance",
                "CAS-mole",
                "molar_flow",
            )
        for c in components:
            row(
                stage_row_id(unit, stage, "eq", c),
                equilibrium_row(
                    vapor_id(unit, stage, c),
                    liquid_id(unit, stage, c),
                    vapor_total_id(unit, stage),
                    liquid_total_id(unit, stage),
                    f"{lnk_keys[stage]}.lnK_{c}",
                ),
                "algebraic",
                "CAS-equilibrium",
                "molar_flow_squared",
            )
        row(
            stage_row_id(unit, stage, "Ldef"),
            definition_row(
                liquid_total_id(unit, stage), tuple(liquid_id(unit, stage, c) for c in components)
            ),
            "algebraic",
            "CAS-Ldef",
            "molar_flow",
        )
        row(
            stage_row_id(unit, stage, "Vdef"),
            definition_row(
                vapor_total_id(unit, stage), tuple(vapor_id(unit, stage, c) for c in components)
            ),
            "algebraic",
            "CAS-Vdef",
            "molar_flow",
        )
        enthalpy_in = (
            *(inlet_keys[TOP] if stage == 1 else liquid_keys[stage - 1]),
            *(inlet_keys[BOTTOM] if stage == count else vapor_keys[stage + 1]),
            *(key for s in sides for key in inlet_keys[s.port]),
        )
        row(
            energy_row_id(unit, stage),
            energy_row(
                enthalpy_in,
                (*vapor_keys[stage], *liquid_keys[stage]),
                source=stage_duty_id(unit, stage),
            ),
            "holdup_balance",
            "CAS-energy",
            "heat_rate",
        )
        row(
            stage_row_id(unit, stage, "P"),
            specification_row(
                stage_pressure_id(unit, stage),
                pin(stage_pressure_id(unit, stage), spec.pressures[stage - 1]),
            ),
            "algebraic",
            "CAS-P",
            "pressure",
        )
        row(
            stage_row_id(unit, stage, "Q"),
            specification_row(
                stage_duty_id(unit, stage),
                pin(stage_duty_id(unit, stage), spec.duties[stage - 1]),
            ),
            "algebraic",
            "CAS-Q",
            "heat_rate",
        )

    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        for c in components:
            column(flow_id(stream, c), "molar_flow")
        column(temperature_id(stream), "temperature")
        column(pressure_id(stream), "pressure")
        for c, value in zip(components, inlet.state.n, strict=True):
            row(
                inlet_row_id(unit, inlet.port, "n", c),
                specification_row(flow_id(stream, c), pin(flow_id(stream, c), value)),
                "algebraic",
                "CAS-inlet-n",
                "molar_flow",
            )
        row(
            inlet_row_id(unit, inlet.port, "T"),
            specification_row(
                temperature_id(stream), pin(temperature_id(stream), inlet.state.temperature)
            ),
            "algebraic",
            "CAS-inlet-T",
            "temperature",
        )
        row(
            inlet_row_id(unit, inlet.port, "P"),
            specification_row(pressure_id(stream), pin(pressure_id(stream), inlet.state.pressure)),
            "algebraic",
            "CAS-inlet-P",
            "pressure",
        )

    return Contribution(
        variable_ids=tuple(variables),
        equations=tuple(equations),
        blocks=tuple(blocks),
        block_inputs=block_inputs,
        parameter_ids=tuple(parameter_ids),
        parameters=parameters,
        variable_kinds=variable_kinds,
        row_kinds=row_kinds,
    )


def declared_problem(rows: Contribution, label: str = MODEL_ID) -> ProblemSpec:
    """The declared rows as a `ProblemSpec`, for the float evaluator (`compile.reference`).

    `label` is a placeholder for evaluation only: the compiled problem's label, which identity
    depends on, is WO-2's to fix.
    """
    problem = ProblemSpec(
        label=label,
        variable_ids=rows.variable_ids,
        equations=rows.equations,
        parameter_ids=rows.parameter_ids,
        parameters=rows.parameters,
        blocks=rows.blocks,
        block_inputs=rows.block_inputs,
        variable_kinds=rows.variable_kinds,
        row_kinds=rows.row_kinds,
    )
    problem.validate()
    return problem
