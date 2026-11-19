"""`syn001.column`'s declared rows: S02 spec §2 (S01's stage rows, the condenser's and the
reboiler's specification rows, a total condenser's block) with S06 §2's inverse rows and the
flowsheet links.

Moved verbatim from `column` (S19 B2), which re-exports every public name here and keeps the regime
forms and the §6 initializer. This module imports only `column_spec` and `column_validation` among
the column modules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import NamedTuple

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
from openflowsheet.models.syn001.cascade_rows import _token
from openflowsheet.models.syn001.cascade_spec import (
    BOTTOM,
    TOP,
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
    EndSpecification,
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
    inlets = spec.inlets()
    for inlet in inlets:
        _token(inlet.port)
    total = spec.total_condenser
    stages = spec.equilibrium_stages()
    slots = spec.slot_stages()

    builder = _ContributionBuilder(
        spec=spec,
        provider=provider,
        context=context,
        links=links,
        unit=unit,
        components=components,
        composition_dependent=composition_dependent,
        inlets=inlets,
        total=total,
        slots=slots,
    )

    keys = builder.property_blocks(stages)
    if total:
        builder.total_condenser_rows(keys)

    sides_at: dict[int, list[PlacedInlet]] = {}
    for inlet in inlets:
        if inlet.port not in (TOP, BOTTOM):
            sides_at.setdefault(inlet.stage, []).append(inlet)

    for stage in stages:
        builder.stage_rows(stage, keys, sides_at.get(stage, []))

    if links is not None:
        _link_rows(spec, links, builder)
        return builder.contribution()

    for inlet in inlets:
        builder.inlet_pin_rows(inlet)

    return builder.contribution()


@dataclass
class _ContributionBuilder:
    """One call of `declared_rows`: its frame and the tables of the `Contribution` it builds
    (playbook rule 6, a builder).

    Frame, fixed for the call and never assigned after construction: `spec`, `provider`,
    `context` and `links` (the call's arguments), `unit`, `components`, `composition_dependent`,
    `inlets`, `total` and `slots` (derived from them before construction).
    State, the product tables, each written only by its append method: `variables` and
    `variable_kinds` by `column`, `equations` and `row_kinds` by `row`, `parameter_ids` and
    `parameters` by `pin`, `blocks` and `block_inputs` by `lnk_block` and `enthalpy_block`.
    On a repeated id (none after `validate`) the lists keep every entry, in append order, and
    the dicts the last one written.
    The phases (`property_blocks`, `total_condenser_rows`, `stage_rows`, `inlet_pin_rows`,
    `contribution`), the helper `slot` they share and `_link_rows` write only through these
    append methods; `contribution` reads the tables last.
    """

    spec: ColumnSpec
    provider: PropertyProvider
    context: EvaluationContext
    links: FlowsheetLinks | None
    unit: str
    components: tuple[str, ...]
    composition_dependent: bool
    inlets: tuple[PlacedInlet, ...]
    total: bool
    slots: dict[int, str]
    variables: list[str] = field(default_factory=list)
    variable_kinds: dict[str, QuantityKind] = field(default_factory=dict)
    equations: list[EquationSpec] = field(default_factory=list)
    row_kinds: dict[str, QuantityKind] = field(default_factory=dict)
    blocks: list[LnKBlock | EnthalpyFlowBlock | GammaPhiLnKBlock | MixtureEnthalpyFlowBlock] = (
        field(default_factory=list)
    )
    block_inputs: dict[str, tuple[str, ...]] = field(default_factory=dict)
    parameter_ids: list[str] = field(default_factory=list)
    parameters: dict[str, float] = field(default_factory=dict)

    def property_blocks(self, stages: tuple[int, ...]) -> _BlockKeys:
        """The blocks, as S01: at a total condenser first its three (`_condenser_blocks`), then
        one lnK and one enthalpy block per (stage, phase) outlet of the equilibrium `stages`
        (`_stage_blocks`), then one per inlet. Returns their output keys."""
        vapor_keys: dict[int, tuple[str, ...]] = {}
        liquid_keys: dict[int, tuple[str, ...]] = {}
        lnk_keys: dict[int, str] = {}
        reflux_keys: tuple[str, ...] = ()
        distillate_keys: tuple[str, ...] = ()
        if self.total:
            lnk_keys[1], reflux_keys, distillate_keys = self._condenser_blocks()
        for stage in stages:
            lnk_keys[stage], vapor_keys[stage], liquid_keys[stage] = self._stage_blocks(stage)
        inlet_keys: dict[str, tuple[str, ...]] = {}
        for inlet in self.inlets:
            stream = inlet_stream(self.unit, inlet.port)
            inlet_keys[inlet.port] = self.enthalpy_block(
                f"{self.unit}_in_{inlet.port}",
                _phase(inlet.state),
                tuple(flow_id(stream, c) for c in self.components),
                temperature_id(stream),
                pressure_id(stream),
            )

        return _BlockKeys(
            lnk=lnk_keys,
            vapor=vapor_keys,
            liquid=liquid_keys,
            reflux=reflux_keys,
            distillate=distillate_keys,
            inlet=inlet_keys,
        )

    def _condenser_blocks(self) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        """A total condenser's blocks at `(T_c, P_c)`: one lnK over `v_2` (the bubble row) and one
        liquid enthalpy block each for `r` and `d`. Returns (lnK id, `r` keys, `d` keys)."""
        t_c, p_c = stage_temperature_id(self.unit, 1), stage_pressure_id(self.unit, 1)
        lnk = self.lnk_block(
            f"{self.unit}_s1",
            t_c,
            p_c,
            tuple(vapor_id(self.unit, 2, c) for c in self.components),
        )
        reflux = self.enthalpy_block(
            f"{self.unit}_s1_r",
            "LIQUID",
            tuple(reflux_id(self.unit, c) for c in self.components),
            t_c,
            p_c,
        )
        distillate = self.enthalpy_block(
            f"{self.unit}_s1_d",
            "LIQUID",
            tuple(distillate_id(self.unit, c) for c in self.components),
            t_c,
            p_c,
        )
        return lnk, reflux, distillate

    def _stage_blocks(self, stage: int) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        """Equilibrium stage j's blocks at `(T_j, P_j)`: one lnK over `l_j` and one vapor and one
        liquid enthalpy block. Returns (lnK id, vapor keys, liquid keys)."""
        token = f"{self.unit}_s{stage}"
        t, p = stage_temperature_id(self.unit, stage), stage_pressure_id(self.unit, stage)
        lnk = self.lnk_block(
            token, t, p, tuple(liquid_id(self.unit, stage, c) for c in self.components)
        )
        vapor = self.enthalpy_block(
            token, "VAPOR", tuple(vapor_id(self.unit, stage, c) for c in self.components), t, p
        )
        liquid = self.enthalpy_block(
            token,
            "LIQUID",
            tuple(liquid_id(self.unit, stage, c) for c in self.components),
            t,
            p,
        )
        return lnk, vapor, liquid

    def lnk_block(self, token: str, t: str, p: str, liquid: tuple[str, ...]) -> str:
        """`liquid`: the flows K is evaluated at (read by a composition-dependent form only)."""
        if self.composition_dependent:
            gamma_phi = GammaPhiLnKBlock(
                self.provider, self.components, self.context, block_id=lnk_block_id(token)
            )
            self.blocks.append(gamma_phi)
            self.block_inputs[gamma_phi.block_id] = (*liquid, t, p)
            return gamma_phi.block_id
        lnk = LnKBlock(self.provider, self.components, self.context, block_id=lnk_block_id(token))
        self.blocks.append(lnk)
        self.block_inputs[lnk.block_id] = (t, p)
        return lnk.block_id

    def enthalpy_block(
        self, token: str, phase: Phase, flows: tuple[str, ...], t: str, p: str
    ) -> tuple[str, ...]:
        block_id = enthalpy_block_id(token, phase)
        block: EnthalpyFlowBlock | MixtureEnthalpyFlowBlock
        if self.composition_dependent:
            block = MixtureEnthalpyFlowBlock(
                self.provider, self.components, phase, self.context, block_id=block_id
            )
        else:
            block = EnthalpyFlowBlock(
                self.provider, self.components, phase, self.context, block_id=block_id
            )
        self.blocks.append(block)
        self.block_inputs[block.block_id] = (*flows, t, p)
        return tuple(f"{block.block_id}.{out}" for out in block.output_ids)

    def total_condenser_rows(self, keys: _BlockKeys) -> None:
        """A total condenser's block (§2.2), over the block keys `keys`: its columns
        (`_condenser_columns`), then rows bal_i, split_i, Ddef, bubble, energy, P, slot."""
        self._condenser_columns()
        for c in self.components:
            self.row(
                stage_row_id(self.unit, 1, "bal", c),
                balance_row(
                    (vapor_id(self.unit, 2, c),),
                    (reflux_id(self.unit, c), distillate_id(self.unit, c)),
                ),
                "holdup_balance",
                "COL-tc-bal",
                "molar_flow",
            )
        for c in self.components:
            self.row(
                stage_row_id(self.unit, 1, "split", c),
                fraction_row(
                    reflux_id(self.unit, c),
                    reflux_fraction_id(self.unit),
                    vapor_id(self.unit, 2, c),
                ),
                "algebraic",
                "COL-tc-split",
                "molar_flow",
            )
        self.row(
            stage_row_id(self.unit, 1, "Ddef"),
            definition_row(
                distillate_total_id(self.unit),
                tuple(distillate_id(self.unit, c) for c in self.components),
            ),
            "algebraic",
            "COL-tc-Ddef",
            "molar_flow",
        )
        self.row(
            stage_row_id(self.unit, 1, "bubble"),
            bubble_row(
                tuple(vapor_id(self.unit, 2, c) for c in self.components),
                tuple(f"{keys.lnk[1]}.lnK_{c}" for c in self.components),
                vapor_total_id(self.unit, 2),
            ),
            "algebraic",
            "COL-tc-bubble",
            "molar_flow",
        )
        self.row(
            energy_row_id(self.unit, 1),
            energy_row(
                keys.vapor[2], (*keys.reflux, *keys.distillate), source=stage_duty_id(self.unit, 1)
            ),
            "holdup_balance",
            "COL-tc-energy",
            "heat_rate",
        )
        self.row(
            stage_row_id(self.unit, 1, "P"),
            specification_row(
                stage_pressure_id(self.unit, 1),
                self.pin(_parameter(stage_pressure_id(self.unit, 1)), self.spec.pressures[0]),
            ),
            "algebraic",
            "COL-tc-P",
            "pressure",
        )
        self.slot(1)

    def _condenser_columns(self) -> None:
        """A total condenser's columns (§2.2): r_i, d_i, phi, D, T_c, P_c, Q_c."""
        for c in self.components:
            self.column(reflux_id(self.unit, c), "molar_flow")
        for c in self.components:
            self.column(distillate_id(self.unit, c), "molar_flow")
        # `phi` is a pure number: the column-only kind `dimensionless`, nominal 1 (§17 item 1).
        self.column(reflux_fraction_id(self.unit), "dimensionless")
        self.column(distillate_total_id(self.unit), "molar_flow")
        self.column(stage_temperature_id(self.unit, 1), "temperature")
        self.column(stage_pressure_id(self.unit, 1), "pressure")
        self.column(stage_duty_id(self.unit, 1), "heat_rate")

    def column(self, name: str, kind: QuantityKind | None) -> None:
        self.variables.append(name)
        if kind is not None:
            self.variable_kinds[name] = kind

    def row(
        self,
        equation_id: str,
        build: RowBuilder,
        accumulation: RowAccumulation,
        family: str,
        kind: QuantityKind,
    ) -> None:
        self.equations.append(
            EquationSpec(
                equation_id=equation_id,
                build=build,
                accumulation=accumulation,
                origin=origin(MODEL_ID, family),
            )
        )
        self.row_kinds[equation_id] = kind

    def pin(self, name: str, value: float) -> str:
        self.parameter_ids.append(name)
        self.parameters[name] = normalize_zero(float(value))
        return name

    def slot(self, stage: int) -> None:
        """Stage j's slot row: `Q_j − Q_j*` (S01's id, `_duty_row`) or the column specification
        (§2.1, its builder from `_slot_build`), then a `purity` end's definition row
        (`_purity_definition`) or, in a flowsheet, a `recovery` end's (`_recovery_definition`)."""
        end = self.slots.get(stage)
        if end is None:
            self._duty_row(stage)
            return
        given = _specification(self.spec, end)
        build = self._slot_build(stage, end, given)
        self.row(
            slot_row_id(self.unit, stage, given.kind),
            build,
            "algebraic",
            _SLOT_FAMILY[given.kind],
            _INVERSE_ROW_KIND.get(
                given.kind, "heat_rate" if given.kind == "duty" else "molar_flow"
            ),
        )
        if given.kind == "purity":
            self._purity_definition(stage, end, given)
        if given.kind == "recovery" and self.links is not None:
            self._recovery_definition(stage, end, given)

    def _duty_row(self, stage: int) -> None:
        """S01's `Q_j − Q_j*` at a stage without a column specification; pins `Q_j*`."""
        duty = self.spec.duties[stage - 1]
        assert duty is not None
        self.row(
            stage_row_id(self.unit, stage, "Q"),
            specification_row(
                stage_duty_id(self.unit, stage),
                self.pin(_parameter(stage_duty_id(self.unit, stage)), duty),
            ),
            "algebraic",
            "CAS-Q",
            "heat_rate",
        )

    def _slot_build(self, stage: int, end: str, given: EndSpecification) -> RowBuilder:
        """The slot row of end `end` at stage j for its specification `given`: a ratio
        (`_ratio_build`), an inverse end's `variable − parameter` (S11 §4.7.4 in a flowsheet,
        S06 §2 otherwise) or `variable − value`; pins its parameter."""
        if given.kind in RATIO_KINDS:
            return self._ratio_build(stage, given)
        if given.kind in INVERSE_KINDS and self.links is not None:
            # S11 §4.7.4: `T_s − T*`, `w − ν*` or `u − π*` with `F_REF` for `F` and `F_c`.
            pinned = (
                recovery_flow_id(self.unit, stage)
                if given.kind == "recovery"
                else slot_column(self.spec, end, given.kind)
            )
            value = given.value if given.kind == "temperature" else given.value * F_REF
            return specification_row(pinned, self.pin(_parameter(pinned), value))
        if given.kind in INVERSE_KINDS:
            # S06 §2: `T_s − T*`, `n_c − ν*` or `u − π*`, each `variable − parameter`.
            pinned = slot_column(self.spec, end, given.kind)
            return specification_row(
                pinned, self.pin(_parameter(pinned), inverse_parameter(self.spec, end))
            )
        pinned = slot_column(self.spec, end, given.kind)
        return specification_row(pinned, self.pin(_parameter(pinned), given.value))

    def _ratio_build(self, stage: int, given: EndSpecification) -> RowBuilder:
        """A ratio slot at stage j: the boilup ratio `V_j / L_j`, or the reflux ratio over the
        total condenser's `r` and `D` or over `L_1` and `V_1`; pins the ratio."""
        ratio = self.pin(ratio_parameter(self.unit, stage, given.kind), given.value)
        if given.kind == "boilup_ratio":
            return ratio_row(
                (vapor_total_id(self.unit, stage),), ratio, liquid_total_id(self.unit, stage)
            )
        if self.total:
            return ratio_row(
                tuple(reflux_id(self.unit, c) for c in self.components),
                ratio,
                distillate_total_id(self.unit),
            )
        return ratio_row((liquid_total_id(self.unit, 1),), ratio, vapor_total_id(self.unit, 1))

    def _purity_definition(self, stage: int, end: str, given: EndSpecification) -> None:
        """S06 §2: a `purity` end's column `u` and its definition `F n_c − u P`, after the slot
        row; `F` is `F_REF` in a flowsheet (S11 §4.7.4)."""
        assert given.component is not None
        scaled = purity_flow_id(self.unit, stage)
        self.column(scaled, "molar_flow")
        self.row(
            stage_row_id(self.unit, stage, "spec", "purity_definition"),
            scaled_definition_row(
                product_flow_id(self.spec, end, given.component),
                self.pin(
                    purity_reference_parameter(self.unit, stage),
                    purity_reference(self.spec) if self.links is None else F_REF,
                ),
                scaled,
                product_total_id(self.spec, end),
            ),
            "algebraic",
            "COL-purity-definition",
            "molar_flow_squared",
        )

    def _recovery_definition(self, stage: int, end: str, given: EndSpecification) -> None:
        """S11 §4.7.4: a flowsheet `recovery` end's column `w` and its definition
        `F_REF n_c − w Σ_k n_{k,c}`, after the slot row; the sum over the inlet columns in
        `inlets()` order."""
        assert given.component is not None
        scaled = recovery_flow_id(self.unit, stage)
        self.column(scaled, "molar_flow")
        self.row(
            stage_row_id(self.unit, stage, "spec", "recovery_definition"),
            scaled_sum_definition_row(
                product_flow_id(self.spec, end, given.component),
                self.pin(recovery_reference_parameter(self.unit, stage), F_REF),
                scaled,
                tuple(
                    flow_id(inlet_stream(self.unit, inlet.port), given.component)
                    for inlet in self.inlets
                ),
            ),
            "algebraic",
            "COL-recovery-definition",
            "molar_flow_squared",
        )

    def stage_rows(self, stage: int, keys: _BlockKeys, sides: list[PlacedInlet]) -> None:
        """Equilibrium stage j's columns and rows, S01's, in S01's order, over the block keys
        `keys` and the side inlets `sides` at the stage: its columns (`_stage_columns`), the
        material and equilibrium rows (`_stage_material_rows`), the energy row
        (`_stage_energy_row`), the pressure row (`_stage_pressure_row`), then the slot row in the
        place of `Q_j − Q_j*`."""
        self._stage_columns(stage)
        self._stage_material_rows(stage, keys)
        self._stage_energy_row(stage, keys, sides)
        self._stage_pressure_row(stage)
        self.slot(stage)

    def _stage_columns(self, stage: int) -> None:
        """Stage j's columns: l_i, v_i, m_i, L, V, T, P, Q."""
        for c in self.components:
            self.column(liquid_id(self.unit, stage, c), "molar_flow")
        for c in self.components:
            self.column(vapor_id(self.unit, stage, c), "molar_flow")
        for c in self.components:
            self.column(mixed_id(self.unit, stage, c), "molar_flow")
        self.column(liquid_total_id(self.unit, stage), "molar_flow")
        self.column(vapor_total_id(self.unit, stage), "molar_flow")
        self.column(stage_temperature_id(self.unit, stage), "temperature")
        self.column(stage_pressure_id(self.unit, stage), "pressure")
        self.column(stage_duty_id(self.unit, stage), "heat_rate")

    def _stage_material_rows(self, stage: int, keys: _BlockKeys) -> None:
        """Stage j's rows mix_i, mole_i and eq_i (over `keys.lnk`), then Ldef and Vdef."""
        for c in self.components:
            self.row(
                stage_row_id(self.unit, stage, "mix", c),
                balance_row(_inflow(self.spec, stage, c), (mixed_id(self.unit, stage, c),)),
                "algebraic",
                "CAS-mix",
                "molar_flow",
            )
        for c in self.components:
            self.row(
                stage_row_id(self.unit, stage, "mole", c),
                balance_row(
                    (mixed_id(self.unit, stage, c),),
                    (vapor_id(self.unit, stage, c), liquid_id(self.unit, stage, c)),
                ),
                "holdup_balance",
                "CAS-mole",
                "molar_flow",
            )
        for c in self.components:
            self.row(
                stage_row_id(self.unit, stage, "eq", c),
                equilibrium_row(
                    vapor_id(self.unit, stage, c),
                    liquid_id(self.unit, stage, c),
                    vapor_total_id(self.unit, stage),
                    liquid_total_id(self.unit, stage),
                    f"{keys.lnk[stage]}.lnK_{c}",
                ),
                "algebraic",
                "CAS-equilibrium",
                "molar_flow_squared",
            )
        self.row(
            stage_row_id(self.unit, stage, "Ldef"),
            definition_row(
                liquid_total_id(self.unit, stage),
                tuple(liquid_id(self.unit, stage, c) for c in self.components),
            ),
            "algebraic",
            "CAS-Ldef",
            "molar_flow",
        )
        self.row(
            stage_row_id(self.unit, stage, "Vdef"),
            definition_row(
                vapor_total_id(self.unit, stage),
                tuple(vapor_id(self.unit, stage, c) for c in self.components),
            ),
            "algebraic",
            "CAS-Vdef",
            "molar_flow",
        )

    def _stage_energy_row(self, stage: int, keys: _BlockKeys, sides: list[PlacedInlet]) -> None:
        """Stage j's energy row: the enthalpy flows from above (`top`, the reflux `r` below a
        total condenser, or `l_{j−1}`), from below (`bottom` or `v_{j+1}`) and of the side
        inlets `sides` in, the stage's vapor and liquid out, with source `Q_j`."""
        above: tuple[str, ...]
        if stage == 1:
            above = keys.inlet[TOP] if self.spec.top is not None else ()
        elif stage == 2 and self.total:
            above = keys.reflux
        else:
            above = keys.liquid[stage - 1]
        below: tuple[str, ...]
        if stage == self.spec.stage_count:
            below = keys.inlet[BOTTOM] if self.spec.bottom is not None else ()
        else:
            below = keys.vapor[stage + 1]
        self.row(
            energy_row_id(self.unit, stage),
            energy_row(
                (*above, *below, *(key for s in sides for key in keys.inlet[s.port])),
                (*keys.vapor[stage], *keys.liquid[stage]),
                source=stage_duty_id(self.unit, stage),
            ),
            "holdup_balance",
            "CAS-energy",
            "heat_rate",
        )

    def _stage_pressure_row(self, stage: int) -> None:
        """Stage j's pressure row `P_j − P_j*`; pins `P_j*`."""
        self.row(
            stage_row_id(self.unit, stage, "P"),
            specification_row(
                stage_pressure_id(self.unit, stage),
                self.pin(
                    _parameter(stage_pressure_id(self.unit, stage)), self.spec.pressures[stage - 1]
                ),
            ),
            "algebraic",
            "CAS-P",
            "pressure",
        )

    def contribution(self) -> Contribution:
        """The `Contribution` of the tables built so far (pure: reads them, in field order of the
        `Contribution`'s keywords as at the base)."""
        return Contribution(
            variable_ids=tuple(self.variables),
            equations=tuple(self.equations),
            blocks=tuple(self.blocks),
            block_inputs=self.block_inputs,
            parameter_ids=tuple(self.parameter_ids),
            parameters=self.parameters,
            variable_kinds=self.variable_kinds,
            row_kinds=self.row_kinds,
        )

    def inlet_pin_rows(self, inlet: PlacedInlet) -> None:
        """An inlet's owned columns n_i, T, P and its pin rows `v − v*` (outside a flowsheet);
        pins the inlet state."""
        stream = inlet_stream(self.unit, inlet.port)
        for c in self.components:
            self.column(flow_id(stream, c), "molar_flow")
        self.column(temperature_id(stream), "temperature")
        self.column(pressure_id(stream), "pressure")
        for c, value in zip(self.components, inlet.state.n, strict=True):
            self.row(
                inlet_row_id(self.unit, inlet.port, "n", c),
                specification_row(
                    flow_id(stream, c), self.pin(_parameter(flow_id(stream, c)), value)
                ),
                "algebraic",
                "CAS-inlet-n",
                "molar_flow",
            )
        self.row(
            inlet_row_id(self.unit, inlet.port, "T"),
            specification_row(
                temperature_id(stream),
                self.pin(_parameter(temperature_id(stream)), inlet.state.temperature),
            ),
            "algebraic",
            "CAS-inlet-T",
            "temperature",
        )
        self.row(
            inlet_row_id(self.unit, inlet.port, "P"),
            specification_row(
                pressure_id(stream),
                self.pin(_parameter(pressure_id(stream)), inlet.state.pressure),
            ),
            "algebraic",
            "CAS-inlet-P",
            "pressure",
        )


class _BlockKeys(NamedTuple):
    """`_ContributionBuilder.property_blocks`'s output keys: `lnk` the lnK block id per stage
    (stage 1 a total condenser's), `vapor` and `liquid` the enthalpy outputs per equilibrium
    stage, `reflux` and `distillate` a total condenser's (empty without one), `inlet` per port.
    A repeated stage or inlet port keeps the entry written last."""

    lnk: dict[int, str]
    vapor: dict[int, tuple[str, ...]]
    liquid: dict[int, tuple[str, ...]]
    reflux: tuple[str, ...]
    distillate: tuple[str, ...]
    inlet: dict[str, tuple[str, ...]]


def _link_rows(spec: ColumnSpec, links: FlowsheetLinks, builder: _ContributionBuilder) -> None:
    """S11 §4.7.3, items 1 and 2: each inlet's owned columns and its link rows (the pin rows'
    ids, kinds and order), then the distillate's and the bottoms' product link rows, written
    through `builder.column` and `builder.row`."""
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
            builder.column(flow_id(internal, c), "molar_flow")
        builder.column(temperature_id(internal), "temperature")
        builder.column(pressure_id(internal), "pressure")
        for c in components:
            builder.row(
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
            builder.row(
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
            builder.row(
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
            builder.row(
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
