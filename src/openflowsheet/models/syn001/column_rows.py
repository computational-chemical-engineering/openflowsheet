"""`syn001.column`'s declared rows: S02 spec §2 (S01's stage rows, the condenser's and the
reboiler's specification rows, a total condenser's block) with S06 §2's inverse rows and the
flowsheet links.

Moved verbatim from `column` (S19 B2), which re-exports every name here and keeps the regime forms
and the §6 initializer. This module imports only `column_spec` and `column_validation` among the
column modules.
"""

from __future__ import annotations

from collections.abc import Callable

from openflowsheet.canonical import normalize_zero
from openflowsheet.compile.spec import EquationSpec, QuantityKind, RowBuilder
from openflowsheet.compiled import EvaluationContext, RowAccumulation
from openflowsheet.models import Contribution, flow_id, origin, pressure_id, temperature_id
from openflowsheet.models.rows import (
    balance_row,
    bubble_row,
    definition_row,
    energy_row,
    equilibrium_row,
    fraction_row,
    ratio_row,
    scaled_definition_row,
    scaled_sum_definition_row,
    specification_row,
)
from openflowsheet.models.syn001.blocks import EnthalpyFlowBlock, LnKBlock
from openflowsheet.models.syn001.cascade import (
    BOTTOM,
    TOP,
    PlacedInlet,
    _parameter,
    _phase,
    _token,
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
from openflowsheet.models.syn001.column_spec import (
    _INVERSE_ROW_KIND,
    _SLOT_FAMILY,
    CONDENSER,
    F_REF,
    INVERSE_KINDS,
    MODEL_ID,
    RATIO_KINDS,
    REBOILER,
    ColumnSpec,
    FlowsheetLinks,
    _specification,
    distillate_id,
    distillate_total_id,
    product_flow_id,
    product_link_row_id,
    product_total_id,
    purity_flow_id,
    purity_reference_parameter,
    ratio_parameter,
    recovery_flow_id,
    recovery_reference_parameter,
    reflux_fraction_id,
    reflux_id,
    slot_column,
    slot_row_id,
)
from openflowsheet.models.syn001.column_validation import inverse_parameter, purity_reference
from openflowsheet.models.syn001.equilibrium_form import equilibrium_form
from openflowsheet.models.syn001.gamma_phi_blocks import GammaPhiLnKBlock, MixtureEnthalpyFlowBlock
from openflowsheet.models.syn001.tp_state import enthalpy_block_id, lnk_block_id
from openflowsheet.thermo import Phase, PropertyProvider

# -- spec §2: declared rows ----------------------------------------------------------------------


def declared_rows(
    spec: ColumnSpec,
    provider: PropertyProvider,
    context: EvaluationContext,
    *,
    links: FlowsheetLinks | None = None,
) -> Contribution:
    """The §2 columns, rows, blocks and pinned inputs: `14 n_eq + (C + 2) n_in + (2C + 5)[total]`
    of each (§3), plus one column `u` and one definition row per `purity` end (S06 §3).

    Stage order, the total condenser's block first when there is one, then each present inlet.
    An equilibrium stage's columns and rows are S01's, in S01's order, with its slot row in the
    place of `Q_j − Q_j*`. Call after `validate`.

    The property blocks dispatch on the provider's equilibrium form (S10-C §4.7): SYN-001 (and any
    provider outside the allow-list) gets `LnKBlock` over `(T_j, P_j)` and per-component
    `EnthalpyFlowBlock`s; a composition-dependent form gets a `GammaPhiLnKBlock` over the stage's
    liquid flows (the total condenser's over `v_2`, the condensate's composition) and single-output
    `MixtureEnthalpyFlowBlock`s. Rows, ids and order are the same for both.

    S11 §4.7.3: with `links` (the column in a flowsheet) each inlet's pin rows become link rows
    `v_stream − v_inlet` under the same ids and kinds, the inlet columns stay owned, and the
    product link rows `<U>:product:<p>:…` follow the inlets. An inverse end takes §4.7.4's form:
    a purity's `F` is `F_REF`, and a recovery's slot is `w − ν*` with `ν* = r* F_REF`, its column
    `w` and its definition row `F_REF n_c − w Σ_k n_{k,c}`. No pinned value is then formed from an
    inlet state, so a `structural_spec` may be passed. `links=None` changes nothing.
    """
    unit, components = _token(spec.unit_id), spec.components
    form = equilibrium_form(provider)
    composition_dependent = form is not None and form.composition_dependent
    count = spec.stage_count
    inlets = spec.inlets()
    for inlet in inlets:
        _token(inlet.port)
    total = spec.total_condenser
    stages = spec.equilibrium_stages()
    slots = spec.slot_stages()

    variables: list[str] = []
    variable_kinds: dict[str, QuantityKind] = {}
    equations: list[EquationSpec] = []
    row_kinds: dict[str, QuantityKind] = {}
    blocks: list[LnKBlock | EnthalpyFlowBlock | GammaPhiLnKBlock | MixtureEnthalpyFlowBlock] = []
    block_inputs: dict[str, tuple[str, ...]] = {}
    parameter_ids: list[str] = []
    parameters: dict[str, float] = {}

    def column(name: str, kind: QuantityKind | None) -> None:
        variables.append(name)
        if kind is not None:
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
        parameter_ids.append(name)
        parameters[name] = normalize_zero(float(value))
        return name

    def enthalpy_block(
        token: str, phase: Phase, flows: tuple[str, ...], t: str, p: str
    ) -> tuple[str, ...]:
        block_id = enthalpy_block_id(token, phase)
        block: EnthalpyFlowBlock | MixtureEnthalpyFlowBlock
        if composition_dependent:
            block = MixtureEnthalpyFlowBlock(
                provider, components, phase, context, block_id=block_id
            )
        else:
            block = EnthalpyFlowBlock(provider, components, phase, context, block_id=block_id)
        blocks.append(block)
        block_inputs[block.block_id] = (*flows, t, p)
        return tuple(f"{block.block_id}.{out}" for out in block.output_ids)

    def lnk_block(token: str, t: str, p: str, liquid: tuple[str, ...]) -> str:
        """`liquid`: the flows K is evaluated at (read by a composition-dependent form only)."""
        if composition_dependent:
            gamma_phi = GammaPhiLnKBlock(
                provider, components, context, block_id=lnk_block_id(token)
            )
            blocks.append(gamma_phi)
            block_inputs[gamma_phi.block_id] = (*liquid, t, p)
            return gamma_phi.block_id
        lnk = LnKBlock(provider, components, context, block_id=lnk_block_id(token))
        blocks.append(lnk)
        block_inputs[lnk.block_id] = (t, p)
        return lnk.block_id

    # Blocks, as S01: one lnK and one enthalpy block per (stage, phase) outlet, one per inlet; at
    # a total condenser one lnK (the bubble row) and one liquid block each for `r` and `d`.
    vapor_keys: dict[int, tuple[str, ...]] = {}
    liquid_keys: dict[int, tuple[str, ...]] = {}
    lnk_keys: dict[int, str] = {}
    reflux_keys: tuple[str, ...] = ()
    distillate_keys: tuple[str, ...] = ()
    if total:
        t_c, p_c = stage_temperature_id(unit, 1), stage_pressure_id(unit, 1)
        lnk_keys[1] = lnk_block(
            f"{unit}_s1", t_c, p_c, tuple(vapor_id(unit, 2, c) for c in components)
        )
        reflux_keys = enthalpy_block(
            f"{unit}_s1_r", "LIQUID", tuple(reflux_id(unit, c) for c in components), t_c, p_c
        )
        distillate_keys = enthalpy_block(
            f"{unit}_s1_d", "LIQUID", tuple(distillate_id(unit, c) for c in components), t_c, p_c
        )
    for stage in stages:
        token = f"{unit}_s{stage}"
        t, p = stage_temperature_id(unit, stage), stage_pressure_id(unit, stage)
        lnk_keys[stage] = lnk_block(
            token, t, p, tuple(liquid_id(unit, stage, c) for c in components)
        )
        vapor_keys[stage] = enthalpy_block(
            token, "VAPOR", tuple(vapor_id(unit, stage, c) for c in components), t, p
        )
        liquid_keys[stage] = enthalpy_block(
            token, "LIQUID", tuple(liquid_id(unit, stage, c) for c in components), t, p
        )
    inlet_keys: dict[str, tuple[str, ...]] = {}
    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        inlet_keys[inlet.port] = enthalpy_block(
            f"{unit}_in_{inlet.port}",
            _phase(inlet.state),
            tuple(flow_id(stream, c) for c in components),
            temperature_id(stream),
            pressure_id(stream),
        )

    def slot(stage: int) -> None:
        """Stage j's slot row: `Q_j − Q_j*` (S01's id) or the column specification (§2.1)."""
        end = slots.get(stage)
        if end is None:
            duty = spec.duties[stage - 1]
            assert duty is not None
            row(
                stage_row_id(unit, stage, "Q"),
                specification_row(
                    stage_duty_id(unit, stage), pin(_parameter(stage_duty_id(unit, stage)), duty)
                ),
                "algebraic",
                "CAS-Q",
                "heat_rate",
            )
            return
        given = _specification(spec, end)
        build: RowBuilder
        if given.kind in RATIO_KINDS:
            ratio = pin(ratio_parameter(unit, stage, given.kind), given.value)
            if given.kind == "boilup_ratio":
                build = ratio_row(
                    (vapor_total_id(unit, stage),), ratio, liquid_total_id(unit, stage)
                )
            elif total:
                build = ratio_row(
                    tuple(reflux_id(unit, c) for c in components), ratio, distillate_total_id(unit)
                )
            else:
                build = ratio_row((liquid_total_id(unit, 1),), ratio, vapor_total_id(unit, 1))
        elif given.kind in INVERSE_KINDS and links is not None:
            # S11 §4.7.4: `T_s − T*`, `w − ν*` or `u − π*` with `F_REF` for `F` and `F_c`.
            pinned = (
                recovery_flow_id(unit, stage)
                if given.kind == "recovery"
                else slot_column(spec, end, given.kind)
            )
            value = given.value if given.kind == "temperature" else given.value * F_REF
            build = specification_row(pinned, pin(_parameter(pinned), value))
        elif given.kind in INVERSE_KINDS:
            # S06 §2: `T_s − T*`, `n_c − ν*` or `u − π*`, each `variable − parameter`.
            pinned = slot_column(spec, end, given.kind)
            build = specification_row(pinned, pin(_parameter(pinned), inverse_parameter(spec, end)))
        else:
            pinned = slot_column(spec, end, given.kind)
            build = specification_row(pinned, pin(_parameter(pinned), given.value))
        row(
            slot_row_id(unit, stage, given.kind),
            build,
            "algebraic",
            _SLOT_FAMILY[given.kind],
            _INVERSE_ROW_KIND.get(
                given.kind, "heat_rate" if given.kind == "duty" else "molar_flow"
            ),
        )
        if given.kind == "purity":
            # S06 §2: the column `u` and its definition `F n_c − u P`, after the slot row.
            assert given.component is not None
            scaled = purity_flow_id(unit, stage)
            column(scaled, "molar_flow")
            row(
                stage_row_id(unit, stage, "spec", "purity_definition"),
                scaled_definition_row(
                    product_flow_id(spec, end, given.component),
                    pin(
                        purity_reference_parameter(unit, stage),
                        purity_reference(spec) if links is None else F_REF,
                    ),
                    scaled,
                    product_total_id(spec, end),
                ),
                "algebraic",
                "COL-purity-definition",
                "molar_flow_squared",
            )
        if given.kind == "recovery" and links is not None:
            # S11 §4.7.4: the column `w` and its definition `F_REF n_c − w Σ_k n_{k,c}`, after the
            # slot row; the sum over the inlet columns in `inlets()` order.
            assert given.component is not None
            scaled = recovery_flow_id(unit, stage)
            column(scaled, "molar_flow")
            row(
                stage_row_id(unit, stage, "spec", "recovery_definition"),
                scaled_sum_definition_row(
                    product_flow_id(spec, end, given.component),
                    pin(recovery_reference_parameter(unit, stage), F_REF),
                    scaled,
                    tuple(
                        flow_id(inlet_stream(unit, inlet.port), given.component) for inlet in inlets
                    ),
                ),
                "algebraic",
                "COL-recovery-definition",
                "molar_flow_squared",
            )

    if total:
        # §2.2: columns r_i, d_i, phi, D, T_c, P_c, Q_c; rows bal_i, split_i, Ddef, bubble,
        # energy, P, slot.
        for c in components:
            column(reflux_id(unit, c), "molar_flow")
        for c in components:
            column(distillate_id(unit, c), "molar_flow")
        # `phi` is a pure number: the column-only kind `dimensionless`, nominal 1 (§17 item 1).
        column(reflux_fraction_id(unit), "dimensionless")
        column(distillate_total_id(unit), "molar_flow")
        column(stage_temperature_id(unit, 1), "temperature")
        column(stage_pressure_id(unit, 1), "pressure")
        column(stage_duty_id(unit, 1), "heat_rate")
        for c in components:
            row(
                stage_row_id(unit, 1, "bal", c),
                balance_row((vapor_id(unit, 2, c),), (reflux_id(unit, c), distillate_id(unit, c))),
                "holdup_balance",
                "COL-tc-bal",
                "molar_flow",
            )
        for c in components:
            row(
                stage_row_id(unit, 1, "split", c),
                fraction_row(reflux_id(unit, c), reflux_fraction_id(unit), vapor_id(unit, 2, c)),
                "algebraic",
                "COL-tc-split",
                "molar_flow",
            )
        row(
            stage_row_id(unit, 1, "Ddef"),
            definition_row(
                distillate_total_id(unit), tuple(distillate_id(unit, c) for c in components)
            ),
            "algebraic",
            "COL-tc-Ddef",
            "molar_flow",
        )
        row(
            stage_row_id(unit, 1, "bubble"),
            bubble_row(
                tuple(vapor_id(unit, 2, c) for c in components),
                tuple(f"{lnk_keys[1]}.lnK_{c}" for c in components),
                vapor_total_id(unit, 2),
            ),
            "algebraic",
            "COL-tc-bubble",
            "molar_flow",
        )
        row(
            energy_row_id(unit, 1),
            energy_row(
                vapor_keys[2], (*reflux_keys, *distillate_keys), source=stage_duty_id(unit, 1)
            ),
            "holdup_balance",
            "COL-tc-energy",
            "heat_rate",
        )
        row(
            stage_row_id(unit, 1, "P"),
            specification_row(
                stage_pressure_id(unit, 1),
                pin(_parameter(stage_pressure_id(unit, 1)), spec.pressures[0]),
            ),
            "algebraic",
            "COL-tc-P",
            "pressure",
        )
        slot(1)

    sides_at: dict[int, list[PlacedInlet]] = {}
    for inlet in inlets:
        if inlet.port not in (TOP, BOTTOM):
            sides_at.setdefault(inlet.stage, []).append(inlet)

    for stage in stages:
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
            row(
                stage_row_id(unit, stage, "mix", c),
                balance_row(_inflow(spec, stage, c), (mixed_id(unit, stage, c),)),
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
        above: tuple[str, ...]
        if stage == 1:
            above = inlet_keys[TOP] if spec.top is not None else ()
        elif stage == 2 and total:
            above = reflux_keys
        else:
            above = liquid_keys[stage - 1]
        below: tuple[str, ...]
        if stage == count:
            below = inlet_keys[BOTTOM] if spec.bottom is not None else ()
        else:
            below = vapor_keys[stage + 1]
        row(
            energy_row_id(unit, stage),
            energy_row(
                (*above, *below, *(key for s in sides for key in inlet_keys[s.port])),
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
                pin(_parameter(stage_pressure_id(unit, stage)), spec.pressures[stage - 1]),
            ),
            "algebraic",
            "CAS-P",
            "pressure",
        )
        slot(stage)

    if links is not None:
        _link_rows(spec, links, column, row)
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

    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        for c in components:
            column(flow_id(stream, c), "molar_flow")
        column(temperature_id(stream), "temperature")
        column(pressure_id(stream), "pressure")
        for c, value in zip(components, inlet.state.n, strict=True):
            row(
                inlet_row_id(unit, inlet.port, "n", c),
                specification_row(flow_id(stream, c), pin(_parameter(flow_id(stream, c)), value)),
                "algebraic",
                "CAS-inlet-n",
                "molar_flow",
            )
        row(
            inlet_row_id(unit, inlet.port, "T"),
            specification_row(
                temperature_id(stream),
                pin(_parameter(temperature_id(stream)), inlet.state.temperature),
            ),
            "algebraic",
            "CAS-inlet-T",
            "temperature",
        )
        row(
            inlet_row_id(unit, inlet.port, "P"),
            specification_row(
                pressure_id(stream), pin(_parameter(pressure_id(stream)), inlet.state.pressure)
            ),
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


def _link_rows(
    spec: ColumnSpec,
    links: FlowsheetLinks,
    column: Callable[[str, QuantityKind | None], None],
    row: Callable[[str, RowBuilder, RowAccumulation, str, QuantityKind], None],
) -> None:
    """S11 §4.7.3, items 1 and 2: each inlet's owned columns and its link rows (the pin rows'
    ids, kinds and order), then the distillate's and the bottoms' product link rows."""
    unit, components, count = spec.unit_id, spec.components, spec.stage_count
    inlets = spec.inlets()
    if set(links.inlets) != {inlet.port for inlet in inlets}:
        raise ValueError(
            f"{unit}: links name inlets {sorted(links.inlets)}, the specification "
            f"{sorted(inlet.port for inlet in inlets)}"
        )
    for inlet in inlets:
        internal, stream = inlet_stream(unit, inlet.port), links.inlets[inlet.port]
        for c in components:
            column(flow_id(internal, c), "molar_flow")
        column(temperature_id(internal), "temperature")
        column(pressure_id(internal), "pressure")
        for c in components:
            row(
                inlet_row_id(unit, inlet.port, "n", c),
                definition_row(flow_id(stream, c), (flow_id(internal, c),)),
                "algebraic",
                "COL-inlet-link",
                "molar_flow",
            )
        quantities: tuple[tuple[str, Callable[[str], str], QuantityKind], ...] = (
            ("T", temperature_id, "temperature"),
            ("P", pressure_id, "pressure"),
        )
        for kind, identify, quantity in quantities:
            row(
                inlet_row_id(unit, inlet.port, kind),
                definition_row(identify(stream), (identify(internal),)),
                "algebraic",
                "COL-inlet-link",
                quantity,
            )
    for product, end, stage, stream in (
        ("distillate", CONDENSER, 1, links.distillate),
        ("bottoms", REBOILER, count, links.bottoms),
    ):
        for c in components:
            row(
                product_link_row_id(unit, product, "n", c),
                definition_row(flow_id(stream, c), (product_flow_id(spec, end, c),)),
                "algebraic",
                "COL-product-link",
                "molar_flow",
            )
        ends: tuple[tuple[str, str, Callable[[str], str], QuantityKind], ...] = (
            ("T", stage_temperature_id(unit, stage), temperature_id, "temperature"),
            ("P", stage_pressure_id(unit, stage), pressure_id, "pressure"),
        )
        for kind, internal, identify, quantity in ends:
            row(
                product_link_row_id(unit, product, kind),
                definition_row(identify(stream), (internal,)),
                "algebraic",
                "COL-product-link",
                quantity,
            )


def _inflow(spec: ColumnSpec, stage: int, c: str) -> tuple[str, ...]:
    """Equilibrium stage j's `mix` inflow of component c, in S01's order: from above (`top`,
    the reflux `r` below a total condenser, or `l_{j−1}`; nothing without a `top` inlet), from
    below (`bottom` or `v_{j+1}`; nothing without a `bottom` inlet), then its side feeds."""
    unit = spec.unit_id
    names: list[str] = []
    if stage == 1:
        if spec.top is not None:
            names.append(flow_id(inlet_stream(unit, TOP), c))
    elif stage == 2 and spec.total_condenser:
        names.append(reflux_id(unit, c))
    else:
        names.append(liquid_id(unit, stage - 1, c))
    if stage == spec.stage_count:
        if spec.bottom is not None:
            names.append(flow_id(inlet_stream(unit, BOTTOM), c))
    else:
        names.append(vapor_id(unit, stage + 1, c))
    names.extend(
        flow_id(inlet_stream(unit, side.port), c) for side in spec.sides if side.stage == stage
    )
    return tuple(names)
